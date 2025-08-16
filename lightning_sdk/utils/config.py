import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

import yaml

_DEFAULT_CONFIG_FILE_PATH = "~/.lightning/config.yaml"


@dataclass
class DefaultConfigKeys:
    """Default configuration keys for the Lightning SDK."""

    organization: str = "organization.name"

    teamspace_name: str = "teamspace.name"
    teamspace_owner: str = "teamspace.owner"
    teamspace_owner_type: str = "teamspace.owner_type"

    machine: str = "machine.name"

    studio: str = "studio.name"


class ConfigProxy:
    def __init__(self, root: "Config", *path: str) -> None:
        self._root = root
        self._path = path  # list of keys from root

    def __getattr__(self, name: str) -> "ConfigProxy":
        """Returns a reference to a nested ConfigProxy object a level deeper in the config hierarchy.

        Args:
            name: the name of the attribute to access, which corresponds to a key in the config.

        Returns:
            ConfigProxy: the next ConfigProxy object for the attribute.
        """
        # Build a deeper path and return a new proxy
        return ConfigProxy(self._root, *self._path, name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Sets the name attribute to value at the current hierarchy level.

        Args:
            name: the attribute name to set, which corresponds to a key in the config.
            value: the value to set for the given attribute name in the config.
        """
        if name in ("_root", "_path"):  # internal attributes
            super().__setattr__(name, value)
        else:
            # Assign a nested value in the root config
            self._root._set_nested([*self._path, name], value)


class Config:
    def __init__(self, config_file: Optional[str] = None) -> None:
        """Config class to manage configuration settings for the lightning SDK and CLI.

        Args:
            config_file: the file path where the configuration is stored.
            If None, defaults to "~/.lightning/config.yaml".
        """
        if config_file is None:
            config_file = _DEFAULT_CONFIG_FILE_PATH
        self._config_file = os.path.expanduser(config_file)

    def _load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self._config_file):
            return {}  # Return empty dict if config doesn't exist
        with open(self._config_file) as f:
            return yaml.safe_load(f) or {}

    def _save_config(self, config: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self._config_file), exist_ok=True)
        with open(self._config_file, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=True)

    def _set_nested(self, keys: Sequence[str], value: str) -> None:
        config = self._load_config()
        curr = config
        for k in keys[:-1]:
            if k not in curr or not isinstance(curr[k], Dict):
                curr[k] = {}
            curr = curr[k]
        curr[keys[-1]] = value
        self._save_config(config)

    def __getattr__(self, name: str) -> ConfigProxy:
        """Returns a proxy to the actual values to allow for nested access.

        Args:
            name: the name of the value to retrieve.

        Returns:
            ConfigProxy: a proxy object that allows nested access to the configuration.
        """
        return ConfigProxy(self, name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Sets the name attribute to value at the root level."""
        if name in ("_config_file",):  # internal attributes
            super().__setattr__(name, value)
        else:
            # Assign a value at the root level
            self._set_nested([name], value)
