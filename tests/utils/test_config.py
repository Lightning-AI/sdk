import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest
import yaml

from lightning_sdk.utils.config import Config, ConfigProxy


@mock.patch("os.path.expanduser")
def test_config_init_default_config_file_path(mock_expanduser):
    """Test Config initialization with default file path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_expanduser.return_value = os.path.join(tmpdir, "config.yaml")
        config = Config()
        expected_path = os.path.join(tmpdir, "config.yaml")
        assert config._config_file == expected_path


def test_config_init_custom_config_file_path():
    """Test Config initialization with custom file path."""
    custom_path = "/custom/path/config.yaml"
    config = Config(custom_path)
    assert config._config_file == custom_path


def test_config_init_expanduser_config_file_path():
    """Test Config initialization expands user home directory."""
    config = Config("~/my_config.yaml")
    assert config._config_file == os.path.expanduser("~/my_config.yaml")


def test_config_load_config_nonexistent_file():
    """Test loading config from non-existent file returns empty dict."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "nonexistent.yaml")
        config = Config(config_path)
        result = config._load_config()
        assert result == {}


def test_config_load_config_existing_empty_file():
    """Test loading config from existing empty file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "empty.yaml")
        Path(config_path).touch()
        config = Config(config_path)
        result = config._load_config()
        assert result == {}


def test_config_load_config_existing_file_with_content():
    """Test loading config from existing file with YAML content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        test_data = {"key1": "value1", "nested": {"key2": "value2"}}

        with open(config_path, "w") as f:
            yaml.safe_dump(test_data, f)

        config = Config(config_path)
        result = config._load_config()
        assert result == test_data


def test_config_load_config_malformed_yaml():
    """Test loading config from file with malformed YAML raises error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "malformed.yaml")

        with open(config_path, "w") as f:
            f.write("invalid: yaml: content:\n  - unclosed")

        config = Config(config_path)
        with pytest.raises(yaml.YAMLError):
            config._load_config()


def test_config_save_config_creates_directory():
    """Test saving config creates parent directories if they don't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "nested", "deep", "config.yaml")
        config = Config(config_path)
        test_data = {"test": "data"}

        config._save_config(test_data)

        assert os.path.exists(config_path)
        with open(config_path) as f:
            saved_data = yaml.safe_load(f)
        assert saved_data == test_data


def test_config_save_config_overwrites_existing_file():
    """Test saving config overwrites existing file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config = Config(config_path)

        # Save initial data
        initial_data = {"initial": "data"}
        config._save_config(initial_data)

        # Save new data
        new_data = {"new": "data"}
        config._save_config(new_data)

        with open(config_path) as f:
            saved_data = yaml.safe_load(f)
        assert saved_data == new_data


def test_config_save_config_yaml_format():
    """Test saved config has proper YAML formatting."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config = Config(config_path)
        test_data = {"z_key": "value", "a_key": "value", "nested": {"b": 2, "a": 1}}

        config._save_config(test_data)

        with open(config_path) as f:
            content = f.read()

        # Check that keys are sorted
        lines = content.strip().split("\n")
        assert lines[0].startswith("a_key:")
        assert "nested:" in content
        assert "z_key:" in content


def test_config_set_nested_single_level():
    """Test setting a single-level nested value."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config = Config(config_path)

        config._set_nested(["key1"], "value1")

        result = config._load_config()
        assert result == {"key1": "value1"}


def test_config_set_nested_multiple_levels():
    """Test setting a multi-level nested value."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config = Config(config_path)

        config._set_nested(["level1", "level2", "level3"], "deep_value")

        result = config._load_config()
        expected = {"level1": {"level2": {"level3": "deep_value"}}}
        assert result == expected


def test_config_set_nested_existing_structure():
    """Test setting nested value in existing config structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config = Config(config_path)

        # Set initial structure
        initial_data = {"existing": {"key": "value"}, "other": "data"}
        config._save_config(initial_data)

        # Add to existing structure
        config._set_nested(["existing", "new_key"], "new_value")

        result = config._load_config()
        expected = {"existing": {"key": "value", "new_key": "new_value"}, "other": "data"}
        assert result == expected


def test_config_set_nested_overwrite_non_dict():
    """Test setting nested value overwrites non-dict intermediate values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config = Config(config_path)

        # Set initial non-dict value
        config._save_config({"key": "string_value"})

        # Overwrite with nested structure
        config._set_nested(["key", "nested"], "new_value")

        result = config._load_config()
        expected = {"key": {"nested": "new_value"}}
        assert result == expected


def test_config_set_nested_empty_keys_list():
    """Test setting nested value with empty keys list raises IndexError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config = Config(config_path)

        with pytest.raises(IndexError):
            config._set_nested([], "value")


def test_config_getattr_returns_config_proxy():
    """Test Config.__getattr__ returns ConfigProxy instance."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config(os.path.join(tmpdir, "test.yaml"))
        proxy = config.some_attribute

        assert isinstance(proxy, ConfigProxy)
        assert proxy._root is config
        assert proxy._path == ("some_attribute",)


def test_config_file_permissions_error():
    """Test handling of permission errors when saving config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "readonly", "config.yaml")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        # Make directory read-only
        os.chmod(os.path.dirname(config_path), 0o444)

        config = Config(config_path)

        try:
            with pytest.raises(PermissionError):
                config._save_config({"test": "data"})
        finally:
            # Restore permissions for cleanup
            os.chmod(os.path.dirname(config_path), 0o755)


def test_config_proxy_init():
    """Test ConfigProxy initialization."""
    config = Config()
    proxy = ConfigProxy(config, "path1", "path2")

    assert proxy._root is config
    assert proxy._path == ("path1", "path2")


def test_config_proxy_getattr_deeper_proxy():
    """Test ConfigProxy.__getattr__ returns deeper proxy."""
    config = Config()
    proxy1 = ConfigProxy(config, "level1")
    proxy2 = proxy1.level2

    assert isinstance(proxy2, ConfigProxy)
    assert proxy2._root is config
    assert proxy2._path == ("level1", "level2")


def test_config_proxy_getattr_chaining():
    """Test ConfigProxy attribute chaining creates proper path."""
    config = Config()
    proxy = ConfigProxy(config)
    deep_proxy = proxy.a.b.c.d

    assert isinstance(deep_proxy, ConfigProxy)
    assert deep_proxy._root is config
    assert deep_proxy._path == ("a", "b", "c", "d")


def test_config_proxy_setattr_internal_attributes():
    """Test ConfigProxy.__setattr__ handles internal attributes correctly."""
    config = Config()
    proxy = ConfigProxy(config, "test")

    # These should not call _set_nested
    proxy._root = config
    proxy._path = ("new", "path")

    assert proxy._root is config
    assert proxy._path == ("new", "path")


def test_config_proxy_setattr_external_attributes():
    """Test ConfigProxy.__setattr__ calls _set_nested for external attributes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config = Config(config_path)
        proxy = ConfigProxy(config, "section")

        proxy.setting = "value"

        result = config._load_config()
        expected = {"section": {"setting": "value"}}
        assert result == expected


def test_config_proxy_setattr_nested_proxy():
    """Test setting attribute on nested ConfigProxy."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config = Config(config_path)

        config.database.host = "localhost"
        config.database.port = "5432"

        result = config._load_config()
        expected = {"database": {"host": "localhost", "port": "5432"}}
        assert result == expected


def test_config_proxy_setattr_overwrite_existing():
    """Test setting attribute overwrites existing value."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config = Config(config_path)

        # Set initial value
        config.setting = "initial"

        # Overwrite
        config.setting = "updated"

        result = config._load_config()
        expected = {"setting": "updated"}
        assert result == expected


def test_config_proxy_complex_nested_assignment():
    """Test complex nested assignments through ConfigProxy."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        config = Config(config_path)

        # Multiple nested assignments
        config.app.database.host = "db.example.com"
        config.app.database.port = 5432
        config.app.cache.redis.host = "redis.example.com"
        config.app.cache.redis.port = 6379
        config.logging.level = "INFO"

        result = config._load_config()
        expected = {
            "app": {
                "database": {"host": "db.example.com", "port": 5432},
                "cache": {"redis": {"host": "redis.example.com", "port": 6379}},
            },
            "logging": {"level": "INFO"},
        }
        assert result == expected


def test_config_integration_full_workflow():
    """Test complete workflow of config creation, modification, and retrieval."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "integration.yaml")
        config = Config(config_path)

        # Set various configuration values
        config.api.url = "https://api.example.com"
        config.api.timeout = 30
        config.database.connections.main.host = "localhost"
        config.database.connections.main.port = 5432
        config.database.connections.backup.host = "backup.example.com"
        config.features.debug = True

        # Verify file was created and contains expected structure
        assert os.path.exists(config_path)

        # Create new config instance to test loading
        config2 = Config(config_path)
        loaded_data = config2._load_config()

        expected = {
            "api": {"url": "https://api.example.com", "timeout": 30},
            "database": {
                "connections": {"main": {"host": "localhost", "port": 5432}, "backup": {"host": "backup.example.com"}}
            },
            "features": {"debug": True},
        }
        assert loaded_data == expected


def test_config_integration_incremental_updates():
    """Test incremental updates to configuration preserve existing values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "incremental.yaml")
        config = Config(config_path)

        # First set of values
        config.section1.key1 = "value1"
        config.section2.nested.key2 = "value2"

        # Second set of values
        config.section1.key3 = "value3"
        config.section3.key4 = "value4"

        result = config._load_config()
        expected = {
            "section1": {"key1": "value1", "key3": "value3"},
            "section2": {"nested": {"key2": "value2"}},
            "section3": {"key4": "value4"},
        }
        assert result == expected


@mock.patch("os.path.expanduser")
def test_config_integration_default_config_location(mock_expanduser):
    """Test default config file location is correctly set."""
    with tempfile.TemporaryDirectory() as tmpdir:
        expected_path = os.path.join(tmpdir, ".lightning", "config.yaml")
        mock_expanduser.return_value = expected_path
        config = Config()
        assert config._config_file == expected_path


def test_config_integration_config_proxy_path_tracking():
    """Test ConfigProxy correctly tracks nested path access."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config(os.path.join(tmpdir, "test.yaml"))

        # Access deeply nested proxy without setting values
        deep_proxy = config.level1.level2.level3.level4

        assert deep_proxy._path == ("level1", "level2", "level3", "level4")
        assert deep_proxy._root is config


def test_config_integration_mixed_data_types():
    """Test configuration handles various data types correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "types.yaml")
        config = Config(config_path)

        # Set various data types
        config.string_val = "hello"
        config.int_val = 42
        config.float_val = 3.14
        config.bool_val = True
        config.list_val = [1, 2, 3]
        config.none_val = None

        result = config._load_config()
        expected = {
            "string_val": "hello",
            "int_val": 42,
            "float_val": 3.14,
            "bool_val": True,
            "list_val": [1, 2, 3],
            "none_val": None,
        }
        assert result == expected


def test_config_edge_cases_special_characters_in_path():
    """Test config handles file paths with special characters."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config with spaces & symbols!.yaml")
        config = Config(config_path)

        config.test = "value"

        assert os.path.exists(config_path)
        result = config._load_config()
        assert result == {"test": "value"}


def test_config_edge_cases_very_deep_nesting():
    """Test config handles very deep nesting levels."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "deep.yaml")
        config = Config(config_path)

        # Create 10 levels deep nesting
        config.l1.l2.l3.l4.l5.l6.l7.l8.l9.l10 = "deep_value"

        result = config._load_config()
        # Navigate to the deep value
        current = result
        for i in range(1, 11):
            current = current[f"l{i}"]
        assert current == "deep_value"


def test_config_edge_cases_unicode_values():
    """Test config handles Unicode values correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "unicode.yaml")
        config = Config(config_path)

        config.unicode_text = "Hello World"
        config.emoji = "rocket"

        result = config._load_config()
        expected = {"unicode_text": "Hello World", "emoji": "rocket"}
        assert result == expected


def test_config_edge_cases_large_values():
    """Test config handles large string values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "large.yaml")
        config = Config(config_path)

        large_string = "x" * 10000
        config.large_value = large_string

        result = config._load_config()
        assert result["large_value"] == large_string


def test_config_edge_cases_numeric_keys_as_strings():
    """Test config handles numeric-like keys correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "numeric.yaml")
        config = Config(config_path)

        # Access attributes that look like numbers
        proxy = getattr(config, "123")
        proxy.setting = "value"

        result = config._load_config()
        expected = {"123": {"setting": "value"}}
        assert result == expected


def test_config_yaml_none_value_handling():
    """Test config handles None values in YAML correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "none_values.yaml")

        # Manually create YAML with null values
        with open(config_path, "w") as f:
            f.write("null_value: null\nstring_value: 'hello'\n")

        config = Config(config_path)
        result = config._load_config()

        assert result["null_value"] is None
        assert result["string_value"] == "hello"


def test_config_yaml_empty_dict_handling():
    """Test config handles empty dictionaries correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "empty_dict.yaml")
        config = Config(config_path)

        # Set empty nested structure
        config._save_config({"empty_section": {}})

        result = config._load_config()
        assert result == {"empty_section": {}}


def test_config_proxy_path_with_empty_root():
    """Test ConfigProxy with empty root path."""
    config = Config()
    proxy = ConfigProxy(config)

    assert proxy._path == ()
    assert proxy._root is config

    # Test accessing attribute creates proper path
    nested = proxy.test
    assert nested._path == ("test",)


def test_config_concurrent_file_access():
    """Test config behavior with concurrent file operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "concurrent.yaml")
        config1 = Config(config_path)
        config2 = Config(config_path)

        # Both configs write to same file
        config1.setting1 = "value1"
        config2.setting2 = "value2"

        # Last write wins
        result = config1._load_config()
        assert "setting2" in result
        # setting1 may or may not be present depending on timing


def test_config_invalid_yaml_structure():
    """Test config behavior when YAML structure is invalid for our use case."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "invalid_structure.yaml")

        # Create YAML that's valid but not a dict at root
        with open(config_path, "w") as f:
            f.write("- item1\n- item2\n")

        config = Config(config_path)
        result = config._load_config()

        # Should load as list, not dict
        assert result == ["item1", "item2"]


def test_config_set_nested_with_list_values():
    """Test setting nested values that contain lists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "list_values.yaml")
        config = Config(config_path)

        config._set_nested(["servers", "hosts"], ["host1", "host2", "host3"])
        config._set_nested(["servers", "ports"], [8080, 8081, 8082])

        result = config._load_config()
        expected = {"servers": {"hosts": ["host1", "host2", "host3"], "ports": [8080, 8081, 8082]}}
        assert result == expected
