from tests.cli.help import assert_help_contains


def test_ai_hub_help() -> None:
    result_text = assert_help_contains(
        "lightning aihub --help",
        "Usage: lightning aihub [OPTIONS] COMMAND [ARGS]...",
        "Browse and launch AI Hub templates.",
        "api-info",
        "deploy",
        "list-apis",
    )
    assert "Commands:" in result_text
    assert "--help" in result_text


def test_aihub_api_info_help() -> None:
    result_text = assert_help_contains(
        "lightning aihub api-info --help",
        "Usage: lightning aihub api-info [OPTIONS] API_ID",
        "Get full API template info such as input details.",
        "lightning aihub api_info API-ID",
        "API-ID: The ID of the API for which information is requested.",
    )
    assert "--help" in result_text


def test_aihub_deploy_help() -> None:
    result_text = assert_help_contains(
        "lightning aihub deploy --help",
        "Usage: lightning aihub deploy [OPTIONS] API_ID",
        "Deploy an API template from the AI Hub.",
        "lightning aihub deploy API-ID",
        "API-ID: The ID of the API which should be deployed.",
        "--cloud-account, --cloud_account TEXT",
        "Cloud Account to deploy the API to.",
        "--name TEXT",
        "Name of the deployed API.",
        "--teamspace TEXT",
        "Teamspace to deploy the API to.",
        "--org TEXT",
        "Organization to deploy the API to.",
    )
    assert "--help" in result_text


def test_aihub_list_apis_help() -> None:
    result_text = assert_help_contains(
        "lightning aihub list-apis --help",
        "Usage: lightning aihub list-apis [OPTIONS]",
        "List API templates available in the AI Hub.",
        "--search TEXT",
        "Search for API templates by name.",
    )
    assert "--help" in result_text
