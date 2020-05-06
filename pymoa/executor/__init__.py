"""Executor
===========

"""
from functools import wraps, partial
from asyncio import iscoroutinefunction
from typing import Tuple

__all__ = ('Executor', 'apply_executor', 'NO_CALLBACK')

NO_CALLBACK = '#@none'


class Executor:

    name = 'Executor'

    supports_coroutine = False

    async def start_executor(self):
        raise NotImplementedError

    async def stop_executor(self, block=True):
        raise NotImplementedError

    async def execute(self, obj, sync_fn, args=(), kwargs=None, callback=None):
        raise NotImplementedError

    @staticmethod
    def call_execute_callback(obj, return_value, callback):
        if callback is None:
            return

        if not isinstance(callback, str):
            callback = callback.__name__
        callback = getattr(obj, callback)
        callback(return_value)

    async def get_echo_clock(self) -> Tuple[int, int, int]:
        raise NotImplementedError


def apply_executor(func=None, callback=None):
    if func is None:
        return partial(apply_executor, callback=callback)

    coro = iscoroutinefunction(func)

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        executor: Executor = getattr(self, 'executor', None)
        if executor is None:
            if coro:
                ret_val = await func(self, *args, **kwargs)
            else:
                ret_val = func(self, *args, **kwargs)
            Executor.call_execute_callback(self, ret_val, callback)
            return ret_val

        if coro and not executor.supports_coroutine:
            raise ValueError(
                f'apply_executor called with async coroutine "{func}", but '
                f'Executor "{executor}" does not support coroutines')
        return await executor.execute(self, func, args, kwargs, callback)

    return wrapper
