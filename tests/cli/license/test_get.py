import os
import subprocess

import yaml


def test_get_help():
    result = subprocess.run("lightning license get --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning license get [OPTIONS] PRODUCT_NAME

  Get a license key for a given product.

Options:
  --config-file TEXT  Path to the config file
  --help              Show this message and exit.
"""
    )


def test_get(tmpdir):
    config_file = os.path.join(tmpdir, "config.yml")
    with open(config_file, "w") as f:
        yaml.dump({"license": {"my-dummy-product": "my-license-key"}}, f)

    result = subprocess.run(
        f"lightning license get my-dummy-product --config-file={config_file}",
        shell=True,
        capture_output=True,
        text=True,
    )
    assert "my-license-key" in (result.stderr + result.stdout)
