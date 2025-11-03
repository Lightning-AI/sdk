import functools
import inspect
import time
import traceback
from abc import ABCMeta
from contextlib import suppress
from typing import Callable, Dict, Tuple

from lightning_sdk.__version__ import __version__
from lightning_sdk.lightning_cloud.openapi import V1CreateSDKCommandHistoryRequest, V1SDKCommandHistorySeverity
from lightning_sdk.lightning_cloud.openapi.models.v1_sdk_command_history_type import V1SDKCommandHistoryType
from lightning_sdk.lightning_cloud.rest_client import LightningClient


def track_calls() -> Callable[..., any]:
    def decorator(func: Callable[..., any]) -> Callable[..., any]:
        @functools.wraps(func)
        def wrapper(*args: Tuple[any, ...], **kwargs: Dict[str, any]) -> any:
            start_time = time.time()
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            args_str = ", ".join(f"{k}: {v}" for k, v in bound_args.arguments.items() if k != "self")
            message = f"VERSION: {__version__} | ARGS: {args_str} "

            body = V1CreateSDKCommandHistoryRequest(
                command=func.__qualname__,
                message=message,
                project_id=None,
                severity=V1SDKCommandHistorySeverity.INFO,
                type=V1SDKCommandHistoryType.SDK,
            )

            try:
                return func(*args, **kwargs)

            except Exception as e:
                body.severity = V1SDKCommandHistorySeverity.ERROR
                body.message += f" | Error: {type(e).__name__}: {e!s} | Traceback: {traceback.format_exc(limit=3)}"
                body.duration = int(time.time() - start_time)
                with suppress(Exception):
                    client = LightningClient(retry=False, max_tries=0)
                    client.s_dk_command_history_service_create_sdk_command_history(body=body)
                raise

        return wrapper

    return decorator


class TrackCallsMeta(type):
    def __new__(cls, name: any, bases: any, attrs: any) -> type.__new__:
        for attr_name, attr_value in attrs.items():
            if attr_name.startswith("__") and attr_name not in ("__init__", "__call__"):
                attrs[attr_name] = attr_value
                continue

            # Noisy
            if attr_name in ("_cls_name"):
                attrs[attr_name] = attr_value
                continue

            if callable(attr_value):
                attrs[attr_name] = track_calls()(attr_value)

            elif isinstance(attr_value, property):
                fget = track_calls()(attr_value.fget) if attr_value.fget else None
                fset = track_calls()(attr_value.fset) if attr_value.fset else None
                fdel = track_calls()(attr_value.fdel) if attr_value.fdel else None
                attrs[attr_name] = property(fget, fset, fdel)

            else:
                attrs[attr_name] = attr_value
        return super().__new__(cls, name, bases, attrs)


class TrackCallsABCMeta(ABCMeta, TrackCallsMeta):
    """Combined metaclass for classes that need both ABC and TrackCalls functionality."""
