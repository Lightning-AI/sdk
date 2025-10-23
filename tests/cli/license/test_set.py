import os
import subprocess

import yaml


def test_set_help():
    result = subprocess.run("lightning license set --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning license set [OPTIONS] PRODUCT_NAME LICENSE_KEY

  Set a license key for a given product.

Options:
  --config-file TEXT  Path to the config file
  --help              Show this message and exit.
"""
    )


def test_set(tmpdir):
    config_file = os.path.join(tmpdir, "config.yml")
    subprocess.run(
        f"lightning license set my-dummy-product my-license-key --config-file={config_file}",
        shell=True,
        capture_output=True,
        text=True,
    )

    with open(config_file) as f:
        cfg = yaml.safe_load(f)
        assert cfg == {"license": {"my-dummy-product": "my-license-key"}}
