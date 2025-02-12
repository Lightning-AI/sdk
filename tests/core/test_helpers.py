import os
from unittest import mock

from tqdm import tqdm


@mock.patch("os.isatty", return_value=False, autospec=True)
@mock.patch.dict(os.environ, {}, clear=True)
def test_tqdm_notty(_):
    from lightning_sdk.helpers import _set_tqdm_envvars_noninteractive

    _set_tqdm_envvars_noninteractive()

    assert "TQDM_POSITION" in os.environ
    assert os.environ["TQDM_POSITION"] == "-1"
    assert "TQDM_MININTERVAL" in os.environ
    assert os.environ["TQDM_MININTERVAL"] == "1"

    pbar = tqdm(range(10))

    assert pbar.mininterval == 1
    assert pbar.pos == 1  # pos is negative position (-(-1))


@mock.patch("os.isatty", return_value=True, autospec=True)
@mock.patch.dict(os.environ, {}, clear=True)
def test_tqdm_tty(_):
    from lightning_sdk.helpers import _set_tqdm_envvars_noninteractive

    _set_tqdm_envvars_noninteractive()

    assert "TQDM_POSITION" not in os.environ
    assert "TQDM_MININTERVAL" not in os.environ
