from lightning_sdk.organization import Organization
from lightning_sdk.teamspace import Teamspace
from lightning_sdk.utils.config import Config, DefaultConfigKeys


def save_teamspace_to_config(teamspace: Teamspace, overwrite: bool = False) -> None:
    _save_to_config_if_not_exists(DefaultConfigKeys.teamspace_name, teamspace.name, overwrite)
    _save_to_config_if_not_exists(DefaultConfigKeys.teamspace_owner, teamspace.owner.name, overwrite)
    _save_to_config_if_not_exists(
        DefaultConfigKeys.teamspace_owner_type,
        "organization" if isinstance(teamspace.owner, Organization) else "user",
        overwrite,
    )


def _save_to_config_if_not_exists(key: str, value: str, overwrite: bool = False) -> None:
    cfg = Config()
    if overwrite or cfg.get(key) is None:
        cfg.set(key, value)
