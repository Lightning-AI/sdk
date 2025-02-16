import subprocess


def test_ai_hub_help():
    result = subprocess.run("lightning aihub --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning aihub [OPTIONS] COMMAND [ARGS]...

  Interact with Lightning Studio - AI Hub.

Options:
  --help  Show this message and exit.

Commands:
  api-info   Get full API template info such as input details.
  deploy     Deploy an API template from the AI Hub.
  list-apis  List API templates available in the AI Hub.
"""
    )


def test_api_info_help():
    result = subprocess.run("lightning aihub api-info --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning aihub api-info [OPTIONS] API_ID

  Get full API template info such as input details.

  Example:   lightning aihub api_info API-ID

  API-ID: The ID of the API for which information is requested.

Options:
  --help  Show this message and exit.
"""
    )


def test_deploy_help():
    result = subprocess.run("lightning aihub deploy --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning aihub deploy [OPTIONS] API_ID

  Deploy an API template from the AI Hub.

  Example:   lightning aihub deploy API-ID

  API-ID: The ID of the API which should be deployed.

Options:
  --cloud-account, --cloud_account TEXT
                                  Cloud Account to deploy the API to. Defaults
                                  to user's default cloud account.
  --name TEXT                     Name of the deployed API. Defaults to the
                                  name of the API template.
  --teamspace TEXT                Teamspace to deploy the API to. Defaults to
                                  user's default teamspace.
  --org TEXT                      Organization to deploy the API to. Defaults
                                  to user's default organization.
  --help                          Show this message and exit.
"""
    )


def test_list_apis_help():
    result = subprocess.run("lightning aihub list-apis --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning aihub list-apis [OPTIONS]

  List API templates available in the AI Hub.

Options:
  --search TEXT  Search for API templates by name.
  --help         Show this message and exit.
"""
    )
