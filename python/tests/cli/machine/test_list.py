from tests.cli.help import assert_help_contains, command_text, mock_command_logging


@mock_command_logging
def test_machine_list_help() -> None:
    assert_help_contains(
        "lightning machine list --help", "Usage: lightning machine list", "Display the list of available machines."
    )


@mock_command_logging
def test_machines_list_help() -> None:
    assert_help_contains(
        "lightning machines list --help", "Usage: lightning machines list", "Display the list of available machines."
    )


@mock_command_logging
def test_list_machines_legacy_help() -> None:
    assert_help_contains(
        "lightning list machines --help",
        "Deprecation warning:",
        "Use `lightning machine list` instead of `lightning list machines`.",
        "Usage: lightning list machines [OPTIONS]",
    )


@mock_command_logging
def test_machines_output() -> None:
    result_text = command_text("lightning machine list")

    assert (
        result_text
        == """┏━━━━━━━━━━━━━━━━━┓
┃ Name            ┃
┡━━━━━━━━━━━━━━━━━┩
│ A100            │
│ A100_X_2        │
│ A100_X_4        │
│ A100_X_8        │
│ B200_X_8        │
│ CPU             │
│ CPU_SMALL       │
│ CPU_X_16        │
│ CPU_X_2         │
│ CPU_X_4         │
│ CPU_X_8         │
│ DATA_PREP       │
│ DATA_PREP_MAX   │
│ DATA_PREP_ULTRA │
│ H100            │
│ H100_X_2        │
│ H100_X_4        │
│ H100_X_8        │
│ H200            │
│ H200_X_8        │
│ L4              │
│ L40S            │
│ L40S_X_2        │
│ L40S_X_4        │
│ L40S_X_8        │
│ L4_X_2          │
│ L4_X_4          │
│ L4_X_8          │
│ RTXP_6000       │
│ RTXP_6000_X_2   │
│ RTXP_6000_X_4   │
│ RTXP_6000_X_8   │
│ T4              │
│ T4_SMALL        │
│ T4_X_2          │
│ T4_X_4          │
│ T4_X_8          │
└─────────────────┘
"""
    )
