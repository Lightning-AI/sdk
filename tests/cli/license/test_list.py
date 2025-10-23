import os
import subprocess

import yaml


def test_list_help():
    result = subprocess.run("lightning license list --help", shell=True, capture_output=True, text=True)
    result_text = result.stdout + result.stderr

    assert (
        result_text
        == """Usage: lightning license list [OPTIONS]

  List configured licenses.

  Example:     lightning license list --include-key

Options:
  --include-key       Print the key as well
  --config-file TEXT  Path to the config file
  --help              Show this message and exit.
"""
    )


def test_list(tmpdir):
    config_file = os.path.join(tmpdir, "config.yml")
    with open(config_file, "w") as f:
        yaml.dump({"license": {"my-dummy-product": "my-license-key", "my-other-product": "second-license-key"}}, f)

    result_with_key = subprocess.run(
        f"lightning license list --include-key --config-file={config_file}", shell=True, capture_output=True, text=True
    )
    result_text_with_key = result_with_key.stderr + result_with_key.stdout

    lines_with_key = result_text_with_key.splitlines()

    result_no_key = subprocess.run(
        f"lightning license list --config-file={config_file}", shell=True, capture_output=True, text=True
    )
    result_text_no_key = result_no_key.stderr + result_no_key.stdout

    lines_no_key = result_text_no_key.splitlines()

    # verify header
    assert "Product" in lines_with_key[1]
    assert "License Key" in lines_with_key[1]
    assert "Product" in lines_no_key[1]
    assert "License Key" in lines_no_key[1]

    # first product license
    assert "my-dummy-product" in lines_with_key[3]
    assert "my-license-key" in lines_with_key[3]
    assert "********" not in lines_with_key[3]

    assert "my-dummy-product" in lines_no_key[3]
    assert "my-license-key" not in lines_no_key[3]
    assert "********" in lines_no_key[3]

    # second product license
    assert "my-other-product" in lines_with_key[4]
    assert "second-license-key" in lines_with_key[4]
    assert "********" not in lines_with_key[4]

    assert "my-other-product" in lines_no_key[4]
    assert "second-license-key" not in lines_no_key[4]
    assert "********" in lines_no_key[4]
