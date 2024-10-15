from functools import lru_cache

from lightning_sdk.api.user_api import UserApi
from lightning_sdk.job.base import _BaseJob
from lightning_sdk.job.v1 import _JobV1
from lightning_sdk.job.v2 import _JobV2
from lightning_sdk.utils.dynamic import ConditionBaseMeta


@lru_cache(maxsize=None)
def _has_jobs_v2() -> bool:
    api = UserApi()
    try:
        return api._get_feature_flags().jobs_v2
    except Exception:
        return False


# having _BaseJob explicitly as base class
# and adding additional base classes before it for MRO
# is required for proper type hinting and autocomplete to work as expected
class Job(_BaseJob, metaclass=ConditionBaseMeta, condition_func=_has_jobs_v2, base_true=_JobV2, base_false=_JobV1):
    pass
