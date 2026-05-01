"""
Comprehensive tests for CLI logging utilities.

This module tests:
- _log_command: Command execution logging to backend
- _notify_exception: User-facing exception formatting and display
- logging_excepthook: Exception hook for CLI error handling
- CommandLoggingGroup: Click Group subclass for automatic command tracking
"""

import contextlib
import sys
from unittest import mock

import click
import click.testing

from lightning_sdk.__version__ import __version__
from lightning_sdk.cli.utils.logging import (
    CommandLoggingGroup,
    _log_command,
    _notify_exception,
    logging_excepthook,
)
from lightning_sdk.lightning_cloud.openapi.models.v1_create_sdk_command_history_request import (
    V1CreateSDKCommandHistoryRequest,
)
from lightning_sdk.lightning_cloud.openapi.models.v1_sdk_command_history_severity import V1SDKCommandHistorySeverity
from lightning_sdk.lightning_cloud.openapi.models.v1_sdk_command_history_type import V1SDKCommandHistoryType


class TestLogCommand:
    """Tests for the _log_command function."""

    @mock.patch("lightning_sdk.cli.utils.logging.LightningClient")
    @mock.patch("lightning_sdk.cli.utils.logging.sys.argv", ["lightning", "studio", "create"])
    def test_log_command_basic(self, mock_client_class):
        """Test basic command logging without error."""
        mock_client = mock.Mock()
        mock_client_class.return_value = mock_client

        _log_command(message="Test message", duration=100)

        mock_client_class.assert_called_once_with(retry=False, max_tries=0)
        mock_client.s_dk_command_history_service_create_sdk_command_history.assert_called_once()
        call_args = mock_client.s_dk_command_history_service_create_sdk_command_history.call_args
        body = call_args.kwargs["body"]

        assert isinstance(body, V1CreateSDKCommandHistoryRequest)
        assert body.command == "lightning studio create"
        assert body.duration == 100
        assert "Test message" in body.message
        assert body.project_id is None
        assert body.severity == V1SDKCommandHistorySeverity.INFO
        assert body.type == V1SDKCommandHistoryType.CLI
        assert body.version == __version__

    @mock.patch("lightning_sdk.cli.utils.logging.LightningClient")
    @mock.patch("lightning_sdk.cli.utils.logging.sys.argv", ["lightning", "studio", "list"])
    def test_log_command_with_warning_error(self, mock_client_class):
        """Test command logging with warning (error='0')."""
        mock_client = mock.Mock()
        mock_client_class.return_value = mock_client

        _log_command(message="Warning occurred", duration=50, error="0")

        call_args = mock_client.s_dk_command_history_service_create_sdk_command_history.call_args
        body = call_args.kwargs["body"]

        assert body.severity == V1SDKCommandHistorySeverity.WARNING
        assert "Warning occurred | Error: 0" in body.message

    @mock.patch("lightning_sdk.cli.utils.logging.LightningClient")
    @mock.patch("lightning_sdk.cli.utils.logging.sys.argv", ["lightning", "job", "run"])
    def test_log_command_with_error(self, mock_client_class):
        """Test command logging with error (error='1' or other)."""
        mock_client = mock.Mock()
        mock_client_class.return_value = mock_client

        _log_command(message="Error occurred", duration=75, error="Connection failed")

        call_args = mock_client.s_dk_command_history_service_create_sdk_command_history.call_args
        body = call_args.kwargs["body"]

        assert body.severity == V1SDKCommandHistorySeverity.ERROR
        assert "Error occurred | Error: Connection failed" in body.message

    @mock.patch("lightning_sdk.cli.utils.logging.LightningClient")
    @mock.patch("lightning_sdk.cli.utils.logging.sys.argv", ["lightning", "test"])
    def test_log_command_message_truncation(self, mock_client_class):
        """Test that long messages are truncated to 1000 characters."""
        mock_client = mock.Mock()
        mock_client_class.return_value = mock_client

        long_message = "A" * 1500  # Message longer than 1000 chars

        _log_command(message=long_message, duration=10)

        call_args = mock_client.s_dk_command_history_service_create_sdk_command_history.call_args
        body = call_args.kwargs["body"]

        assert len(body.message) == 1000

    @mock.patch("lightning_sdk.cli.utils.logging.LightningClient")
    @mock.patch("lightning_sdk.cli.utils.logging.sys.argv", ["lightning"])
    def test_log_command_empty_message(self, mock_client_class):
        """Test command logging with empty message."""
        mock_client = mock.Mock()
        mock_client_class.return_value = mock_client

        _log_command()

        call_args = mock_client.s_dk_command_history_service_create_sdk_command_history.call_args
        body = call_args.kwargs["body"]

        assert body.message == ""
        assert body.duration == 0


class TestNotifyException:
    """Tests for the _notify_exception function."""

    @mock.patch.dict("os.environ", {}, clear=True)
    @mock.patch("lightning_sdk.cli.utils.logging.click.echo")
    def test_notify_exception_without_debug(self, mock_echo):
        """Test exception notification without debug mode."""
        try:
            raise ValueError("This is a test error")
        except ValueError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            _notify_exception(exc_type, exc_value, exc_tb)

        mock_echo.assert_called_once()
        output = mock_echo.call_args[0][0]

        assert "ValueError" in output
        assert "This is a test error" in output
        assert "LIGHTNING_DEBUG=1" in output
        assert "Need help?" in output
        assert "Full traceback" not in output

    @mock.patch.dict("os.environ", {"LIGHTNING_DEBUG": "1"})
    @mock.patch("lightning_sdk.cli.utils.logging._LIGHTNING_DEBUG", True)
    @mock.patch("lightning_sdk.cli.utils.logging.click.echo")
    def test_notify_exception_with_debug(self, mock_echo):
        """Test exception notification with debug mode enabled."""
        try:
            raise RuntimeError("Debug test error")
        except RuntimeError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            _notify_exception(exc_type, exc_value, exc_tb)

        mock_echo.assert_called_once()
        output = mock_echo.call_args[0][0]

        assert "RuntimeError" in output
        assert "Debug test error" in output
        assert "Full traceback" in output
        assert "set: LIGHTNING_DEBUG=1" not in output

    @mock.patch.dict("os.environ", {}, clear=True)
    @mock.patch("lightning_sdk.cli.utils.logging.click.echo")
    def test_notify_exception_with_no_args(self, mock_echo):
        """Test exception notification when exception has no args."""
        try:
            raise ValueError()
        except ValueError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            _notify_exception(exc_type, exc_value, exc_tb)

        mock_echo.assert_called_once()
        output = mock_echo.call_args[0][0]

        assert "ValueError" in output

    @mock.patch.dict("os.environ", {}, clear=True)
    @mock.patch("lightning_sdk.cli.utils.logging.click.echo")
    def test_notify_exception_with_empty_message(self, mock_echo):
        """Test exception notification when exception has empty string message."""
        try:
            raise ValueError("")
        except ValueError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            _notify_exception(exc_type, exc_value, exc_tb)

        mock_echo.assert_called_once()
        output = mock_echo.call_args[0][0]

        assert "ValueError" in output


class TestLoggingExcepthook:
    """Tests for the logging_excepthook function."""

    @mock.patch("lightning_sdk.cli.utils.logging._notify_exception")
    @mock.patch("lightning_sdk.cli.utils.logging._log_command")
    def test_logging_excepthook_with_context(self, mock_log_command, mock_notify):
        """Test excepthook with click context available."""
        cmd = click.Command("test-command")
        ctx = click.Context(cmd, info_name="lightning")
        ctx.parent = None

        with ctx:
            try:
                raise ValueError("Test error in context")
            except ValueError:
                exc_type, exc_value, exc_tb = sys.exc_info()
                logging_excepthook(exc_type, exc_value, exc_tb)

        mock_log_command.assert_called_once()
        logged_message = mock_log_command.call_args.kwargs["message"]

        assert "lightning" in logged_message
        assert "ValueError" in logged_message
        assert "Test error in context" in logged_message
        mock_notify.assert_called_once_with(exc_type, exc_value, exc_tb)

    @mock.patch("lightning_sdk.cli.utils.logging._notify_exception")
    @mock.patch("lightning_sdk.cli.utils.logging._log_command")
    def test_logging_excepthook_without_context(self, mock_log_command, mock_notify):
        """Test excepthook without click context."""
        try:
            raise RuntimeError("Test error without context")
        except RuntimeError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            logging_excepthook(exc_type, exc_value, exc_tb)

        mock_log_command.assert_called_once()
        logged_message = mock_log_command.call_args.kwargs["message"]
        assert "outside_command_context" in logged_message
        assert "RuntimeError" in logged_message
        assert "Test error without context" in logged_message

        mock_notify.assert_called_once_with(exc_type, exc_value, exc_tb)

    @mock.patch("lightning_sdk.cli.utils.logging._notify_exception")
    @mock.patch("lightning_sdk.cli.utils.logging._log_command")
    def test_logging_excepthook_always_notifies(self, mock_log_command, mock_notify):
        """Test that exception notification happens even if logging fails."""
        mock_log_command.side_effect = Exception("Logging failed")

        try:
            raise ValueError("Test error")
        except ValueError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            with contextlib.suppress(Exception):
                logging_excepthook(exc_type, exc_value, exc_tb)

        mock_notify.assert_called_once_with(exc_type, exc_value, exc_tb)


class TestCommandLoggingGroup:
    """Tests for the CommandLoggingGroup class."""

    def test_format_ctx_with_boolean_flags(self):
        """Test context formatting with boolean flags."""

        @click.group(cls=CommandLoggingGroup)
        @click.option("--verbose", is_flag=True)
        @click.option("--quiet", is_flag=True)
        @click.option("--debug", is_flag=False)
        def dummy_group(verbose, quiet, debug):
            pass

        group = CommandLoggingGroup()

        ctx = click.Context(dummy_group, info_name="lightning")
        ctx.params = {"verbose": True, "quiet": False, "debug": None}
        ctx.invoked_subcommand = None
        ctx.args = []

        formatted = group._format_ctx(ctx)

        assert "lightning" in formatted
        assert "--verbose" in formatted
        assert "--quiet" not in formatted  # False should not appear
        assert "--debug" not in formatted  # None should not appear

    def test_format_ctx_with_values(self):
        """Test context formatting with option values."""

        @click.group(cls=CommandLoggingGroup)
        @click.option("--name")
        @click.option("--count", type=int)
        def dummy_group(name, count):
            pass

        group = CommandLoggingGroup()

        ctx = click.Context(dummy_group, info_name="lightning")
        ctx.params = {"name": "test-name", "count": 5}
        ctx.invoked_subcommand = "subcommand"
        ctx.args = ["arg1", "arg2"]

        formatted = group._format_ctx(ctx)

        assert "lightning" in formatted
        assert "--name test-name" in formatted
        assert "--count 5" in formatted
        assert "subcommand" in formatted
        assert "arg1 arg2" in formatted

    @mock.patch("lightning_sdk.cli.utils.logging._log_command")
    def test_invoke_success(self, mock_log_command):
        """Test successful command invocation logs correctly."""

        @click.group(cls=CommandLoggingGroup)
        @click.option("--test", default="value")
        def dummy_group(test):
            pass

        @dummy_group.command()
        def subcommand():
            click.echo("success")

        runner = click.testing.CliRunner()
        result = runner.invoke(dummy_group, ["--test", "myvalue", "subcommand"])

        assert result.exit_code == 0

        mock_log_command.assert_called_once()
        call_kwargs = mock_log_command.call_args.kwargs

        assert "message" in call_kwargs
        assert "duration" in call_kwargs
        assert "error" in call_kwargs
        assert call_kwargs["error"] is None

    @mock.patch("lightning_sdk.cli.utils.logging._log_command")
    def test_invoke_with_click_exception(self, mock_log_command):
        """Test command invocation with ClickException logs error."""

        @click.group(cls=CommandLoggingGroup)
        def dummy_group():
            pass

        @dummy_group.command()
        def subcommand():
            raise click.ClickException("Test click error")

        runner = click.testing.CliRunner()
        result = runner.invoke(dummy_group, ["subcommand"])

        assert result.exit_code == 1

        mock_log_command.assert_called_once()
        call_kwargs = mock_log_command.call_args.kwargs

        assert call_kwargs["error"] == "Test click error"
        assert call_kwargs["duration"] >= 0

    @mock.patch("lightning_sdk.cli.utils.logging._log_command")
    def test_invoke_with_generic_exception(self, mock_log_command):
        """Test command invocation with generic exception logs error."""

        @click.group(cls=CommandLoggingGroup)
        def dummy_group():
            pass

        @dummy_group.command()
        def subcommand():
            raise ValueError("Test generic error")

        runner = click.testing.CliRunner()

        with contextlib.suppress(ValueError):
            runner.invoke(dummy_group, ["subcommand"], catch_exceptions=False)

        mock_log_command.assert_called_once()
        call_kwargs = mock_log_command.call_args.kwargs

        assert call_kwargs["error"] == "Test generic error"
        assert call_kwargs["duration"] >= 0

    @mock.patch("lightning_sdk.cli.utils.logging._log_command")
    def test_invoke_timing(self, mock_log_command):
        """Test that invoke measures command duration."""
        import time

        @click.group(cls=CommandLoggingGroup)
        def dummy_group():
            pass

        @dummy_group.command()
        def subcommand():
            time.sleep(0.01)

        runner = click.testing.CliRunner()
        runner.invoke(dummy_group, ["subcommand"])

        mock_log_command.assert_called_once()
        call_kwargs = mock_log_command.call_args.kwargs

        assert call_kwargs["duration"] >= 0
        assert isinstance(call_kwargs["duration"], int)

    def test_format_ctx_empty_params(self):
        """Test context formatting with no parameters."""

        @click.group(cls=CommandLoggingGroup)
        def dummy_group():
            pass

        group = CommandLoggingGroup()
        ctx = click.Context(dummy_group, info_name="lightning")
        ctx.params = {}
        ctx.invoked_subcommand = None
        ctx.args = []

        formatted = group._format_ctx(ctx)

        assert "lightning" in formatted
        assert "Params:" in formatted
        assert "Args:" in formatted

    @mock.patch("lightning_sdk.cli.utils.logging._log_command")
    def test_invoke_preserves_return_value(self, mock_log_command):
        """Test that invoke preserves the command return value."""

        @click.group(cls=CommandLoggingGroup)
        def dummy_group():
            pass

        @dummy_group.command()
        def subcommand():
            click.echo("Hello")
            return 42

        runner = click.testing.CliRunner()
        result = runner.invoke(dummy_group, ["subcommand"])

        assert result.exit_code == 0
        assert "Hello" in result.output
