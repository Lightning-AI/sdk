from tests.cli.help import assert_help_contains


def test_config_set_help() -> None:
    assert_help_contains("lightning config set --help", "Usage: lightning config set", "Set configuration values.")


def test_config_set_cloud_account_help() -> None:
    assert_help_contains(
        "lightning config set cloud-account --help",
        "Usage: lightning config set cloud-account",
        "Set the default cloud account name in the config.",
    )


def test_config_set_cloud_provider_help() -> None:
    assert_help_contains(
        "lightning config set cloud-provider --help",
        "Usage: lightning config set cloud-provider",
        "Set the default cloud provider name in the config.",
    )


def test_config_set_org_help() -> None:
    assert_help_contains(
        "lightning config set org --help",
        "Usage: lightning config set org",
        "Set the default organization name in the config.",
    )


def test_config_set_studio_help() -> None:
    assert_help_contains(
        "lightning config set studio --help",
        "Usage: lightning config set studio",
        "Set the default studio name in the config.",
    )


def test_config_set_teamspace_help() -> None:
    assert_help_contains(
        "lightning config set teamspace --help",
        "Usage: lightning config set teamspace",
        "Set the default teamspace name in the config.",
    )


def test_config_set_user_help() -> None:
    assert_help_contains(
        "lightning config set user --help",
        "Usage: lightning config set user",
        "Set the default user name in the config.",
    )
