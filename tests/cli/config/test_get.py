from tests.cli.help import assert_help_contains


def test_config_get_help() -> None:
    assert_help_contains("lightning config get --help", "Usage: lightning config get", "Get configuration values.")


def test_config_get_cloud_account_help() -> None:
    assert_help_contains(
        "lightning config get cloud-account --help",
        "Usage: lightning config get cloud-account",
        "Get the default cloud account name from the config.",
    )


def test_config_get_cloud_provider_help() -> None:
    assert_help_contains(
        "lightning config get cloud-provider --help",
        "Usage: lightning config get cloud-provider",
        "Get the default cloud provider name from the config.",
    )


def test_config_get_org_help() -> None:
    assert_help_contains(
        "lightning config get org --help",
        "Usage: lightning config get org",
        "Get the default organization name from the config.",
    )


def test_config_get_studio_help() -> None:
    assert_help_contains(
        "lightning config get studio --help",
        "Usage: lightning config get studio",
        "Get the default studio name from the config.",
    )


def test_config_get_teamspace_help() -> None:
    assert_help_contains(
        "lightning config get teamspace --help",
        "Usage: lightning config get teamspace",
        "Get the default teamspace name from the config.",
    )


def test_config_get_user_help() -> None:
    assert_help_contains(
        "lightning config get user --help",
        "Usage: lightning config get user",
        "Get the default user name from the config.",
    )
