import os
import socket
import sys

import click

_PATH_HERE = os.path.abspath(os.path.dirname(__file__))
_PATH_ROOT = os.path.realpath(os.path.join(_PATH_HERE, "..", ".."))
sys.path.insert(0, _PATH_HERE)
sys.path.insert(0, _PATH_ROOT)

# The legacy forwarding commands intentionally exit with a migration error when
# invoked. Keep them out of the generated reference while documenting the
# supported noun-first command tree.
os.environ["LIGHTNING_EXPERIMENTAL_CLI_ONLY"] = "1"

import lightning_sdk  # noqa: E402
from lightning_sdk.cli.entrypoint import main_cli as _main_cli  # noqa: E402
from _reference import ReferenceDirective  # noqa: E402

_CLI_ARGUMENT_HELP = {
    ("lightning config set user", "user_name"): "User name to make active in the local Lightning CLI config.",
    ("lightning config set org", "org_name"): "Organization name to make active in the local Lightning CLI config.",
    ("lightning config set studio", "studio_name"): "Studio name to make active in the local Lightning CLI config.",
    ("lightning config set teamspace", "teamspace_name"): (
        "Teamspace name to make active in the local Lightning CLI config."
    ),
    ("lightning config set cloud-account", "cloud_account_name"): (
        "Cloud account name to make active in the local Lightning CLI config."
    ),
    ("lightning config set cloud-provider", "cloud_provider_name"): (
        "Cloud provider name to make active in the local Lightning CLI config."
    ),
    ("lightning job inspect", "name"): "Job name to inspect.",
    ("lightning job stop", "name"): "Job name to stop.",
    ("lightning job delete", "name"): "Job name to delete.",
    ("lightning mmt stop", "name"): "Multi-machine training run name to stop.",
    ("lightning mmt delete", "name"): "Multi-machine training run name to delete.",
    ("lightning api deploy", "script_path"): "Path to the LitServe server script to deploy.",
    ("lightning api dockerize", "server_filename"): "Path to the LitServe server file to package as an image.",
    ("lightning api __request", "path"): "API route path to request.",
    ("lightning deployment create", "name"): "Optional deployment name. Lightning generates one if omitted.",
    ("lightning deployment inspect", "name"): "Deployment name to inspect.",
    ("lightning deployment update", "name"): "Deployment name to update.",
    ("lightning deployment delete", "name"): "Deployment name to delete.",
    ("lightning deployment logs", "name"): "Deployment name whose logs should be shown.",
    ("lightning deployment reload-weights", "name"): "Deployment name whose weights should be reloaded.",
    ("lightning container upload", "container"): "Container name to upload.",
    ("lightning container download", "container"): "Container name to download.",
    ("lightning container delete", "name"): "Container name to delete.",
    ("lightning model upload", "name"): "Model name to upload.",
    ("lightning model download", "name"): "Model name to download.",
    ("lightning api-key delete", "key_id"): "API key ID to delete.",
    ("lightning file upload", "path"): "Local file path to upload.",
    ("lightning file download", "path"): "Remote file path to download.",
    ("lightning folder upload", "path"): "Local folder path to upload.",
    ("lightning folder download", "path"): "Remote folder path to download.",
    ("lightning studio connect", "name"): "Optional Studio name to connect to.",
    ("lightning studio cp", "source"): "Source path in the Studio filesystem.",
    ("lightning studio cp", "destination"): "Destination path in the Studio filesystem.",
    ("lightning studio ls", "path"): "Studio filesystem path to list.",
    ("lightning studio rm", "path"): "Studio filesystem path to remove.",
    ("lightning studio open", "path"): "Local path to open in Lightning Studio.",
    ("lightning sandbox update", "sandbox_id"): "Sandbox ID to update.",
    ("lightning sandbox delete", "sandbox_id"): "Sandbox ID to delete.",
    ("lightning sandbox stop", "sandbox_id"): "Sandbox ID to stop.",
    ("lightning sandbox start", "sandbox_id"): "Sandbox ID to start.",
    ("lightning sandbox run", "sandbox_id"): "Sandbox ID where the command should run.",
    ("lightning sandbox run", "command_args"): "Command and arguments to run in the sandbox.",
    ("lightning sandbox logs", "sandbox_id"): "Sandbox ID that owns the command.",
    ("lightning sandbox logs", "command_id"): "Sandbox command ID whose logs should be shown.",
    ("lightning sandbox command", "sandbox_id"): "Sandbox ID that owns the command.",
    ("lightning sandbox command", "command_id"): "Sandbox command ID to inspect.",
    ("lightning sandbox snapshot get", "snapshot_id"): "Snapshot ID to inspect.",
    ("lightning sandbox snapshot create", "sandbox_id"): "Sandbox ID to snapshot.",
    ("lightning sandbox snapshot delete", "snapshot_id"): "Snapshot ID to delete.",
    ("lightning sandbox commands", "sandbox_id"): "Sandbox ID whose command history should be listed.",
    ("lightning license get", "product_name"): "Product name whose license should be shown.",
    ("lightning license set", "product_name"): "Product name for the license.",
    ("lightning license set", "license_key"): "License key value to store.",
    ("lightning license download", "name"): "License name to download.",
    ("lightning cp", "source"): "Source path to copy.",
    ("lightning cp", "destination"): "Optional destination path.",
    ("lightning open", "path"): "Local path to open in Lightning Studio.",
}


def _apply_cli_argument_help(command: click.Command, command_path: str) -> None:
    for param in command.params:
        if isinstance(param, click.Argument):
            help_text = _CLI_ARGUMENT_HELP.get((command_path, param.name))
            if help_text:
                param.help = help_text

    if isinstance(command, click.Group):
        for name, subcommand in command.commands.items():
            _apply_cli_argument_help(subcommand, f"{command_path} {name}")


_apply_cli_argument_help(_main_cli, "lightning")


project = "Lightning SDK"
copyright = "Lightning AI"  # noqa: A001
author = "Lightning AI"
version = lightning_sdk.__version__
release = lightning_sdk.__version__

needs_sphinx = "8.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.doctest",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.todo",
    "sphinx_autodoc_typehints",
    "click_extra.sphinx",
    "sphinx_copybutton",
    "sphinx_paramlinks",
    "sphinx_togglebutton",
]

click_extra_enable_exec_directives = True

templates_path = ["_templates"]

source_suffix = {
    ".rst": "restructuredtext",
}

master_doc = "index"
language = "en"
exclude_patterns = ["_build", "_templates"]
pygments_style = None

html_theme = "pydata_sphinx_theme"
html_theme_options = {
    "github_url": "https://github.com/Lightning-AI/lightning-sdk",
    "show_toc_level": 2,
}

html_static_path = ["_static"]
htmlhelp_basename = "lightning-sdk-doc"


def _can_resolve_host(hostname: str) -> bool:
    try:
        socket.getaddrinfo(hostname, 443)
    except OSError:
        return False
    return True


if all(_can_resolve_host(host) for host in ("docs.python.org", "pytorch.org")):
    intersphinx_mapping = {
        "python": ("https://docs.python.org/3", None),
        "torch": ("https://pytorch.org/docs/stable/", None),
    }
else:
    intersphinx_mapping = {}

nitpicky = True
nitpick_ignore = [
    ("py:class", "typing.Any"),
    ("py:data", "typing.Any"),
    ("py:data", "typing.Optional"),
    ("py:data", "typing.Union"),
    ("py:class", "pathlib.Path"),
    ("py:class", "pathlib._local.Path"),
    ("py:class", "enum.Enum"),
    # base / internal types not worth documenting separately
    ("py:class", "Auth"),
    ("py:class", "lightning_sdk.api.deployment_api.Auth"),
    ("py:class", "MachineDict"),
]
nitpick_ignore_regex = [
    # private / internal base classes
    ("py:class", r".*\._\w+"),
    # generated openapi types (full path)
    ("py:class", r"lightning_sdk\.lightning_cloud\..*"),
    # V1* and Externalv1* openapi short names
    ("py:class", r"V1\w+"),
    ("py:class", r"Externalv1\w+"),
]

autosummary_generate = True
autodoc_member_order = "groupwise"
autoclass_content = "both"
autodoc_typehints = "description"
typehints_description_target = "documented_params"

autodoc_default_options = {
    "members": True,
    "methods": True,
    "special-members": "__call__",
    "exclude-members": "_abc_impl",
    "show-inheritance": True,
}

autosectionlabel_prefix_document = True
autosectionlabel_maxdepth = 1

autodoc_mock_imports = [
    "lightning_cloud",
    "requests",
    "docker",
    "fastapi",
    "uvicorn",
    "simple_term_menu",
    "rich",
    "tqdm",
    "backoff",
]
copybutton_prompt_text = ">>> "
copybutton_prompt_text1 = "... "
copybutton_only_copy_prompt_lines = True

linkcheck_anchors = False
linkcheck_timeout = 60
linkcheck_retries = 3
linkcheck_ignore = [
    r"https://lightning\.ai/.*",
]


def setup(app) -> None:  # noqa: ANN001
    app.add_css_file("main.css")
    app.add_directive("lightning-reference", ReferenceDirective)
