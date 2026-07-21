from importlib.metadata import version
from pathlib import Path

import tomllib

from lightning_sdk.__version__ import __version__


def test_pyproject_uses_setuptools_scm() -> None:
    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())

    assert "setuptools>=80" in pyproject["build-system"]["requires"]
    assert "setuptools-scm>=9.2" in pyproject["build-system"]["requires"]
    assert pyproject["tool"]["setuptools_scm"]["root"] == ".."
    assert "dynamic" not in pyproject["tool"]["setuptools"]


def test_runtime_version_comes_from_distribution_metadata() -> None:
    assert __version__ == version("lightning-sdk")
