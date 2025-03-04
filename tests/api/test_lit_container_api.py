from unittest.mock import MagicMock

from lightning_sdk.api.lit_container_api import LCRAuthFailedError, retry_on_lcr_auth_failure


def test_retry_on_lcr_auth_failure_generator():
    items = [1, 2, 3, 4, 5]

    class Test:
        @retry_on_lcr_auth_failure
        def _gen_fn(self):
            while items:
                i = items.pop(0)
                yield i
                if i == 3:
                    raise LCRAuthFailedError()

    api = Test()
    api.authenticate = MagicMock(return_value=True)
    assert list(api._gen_fn()) == [1, 2, 3, 4, 5]
    api.authenticate.assert_called_once()


def test_retry_on_lcr_auth_failure():
    items = [1, 2]

    class Test:
        @retry_on_lcr_auth_failure
        def _gen_fn(self):
            i = items.pop(0)
            if i == 1:
                raise LCRAuthFailedError()
            return i

    api = Test()
    api.authenticate = MagicMock(return_value=True)
    assert api._gen_fn() == 2
    api.authenticate.assert_called_once()
