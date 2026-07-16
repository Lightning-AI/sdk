import os
import socket
import sys

_PATH_HERE = os.path.abspath(os.path.dirname(__file__))
_PATH_ROOT = os.path.realpath(os.path.join(_PATH_HERE, "..", ".."))
sys.path.insert(0, _PATH_ROOT)

import lightning_sdk  # noqa: E402
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
    "sphinx_copybutton",
    "sphinx_paramlinks",
    "sphinx_togglebutton",
    "myst_parser",
]

templates_path = ["_templates"]

myst_heading_anchors = 3

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
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
