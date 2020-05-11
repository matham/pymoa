"""Executor
===========

"""
import contextlib
import trio
from async_generator import aclosing
from functools import wraps, partial
from asyncio import iscoroutinefunction
from inspect import isgeneratorfunction, isasyncgenfunction
from typing import Tuple, AsyncGenerator

__all__ = (
    'Executor', 'apply_executor', 'apply_generator_executor', 'NO_CALLBACK')

NO_CALLBACK = '#@none'
"""Can be used with :func:`apply_executor` to indicate that no callback should
be used.
"""


class Executor:
    """Executor that can be used to execute a method in a different context,
    e.g. in a different thread or across the network in a server.
    """

    name = 'Executor'

    supports_coroutine = False

    supports_non_coroutine = True

    async def start_executor(self):
        raise NotImplementedError

    async def stop_executor(self, block=True):
        raise NotImplementedError

    async def execute(self, obj, sync_fn, args=(), kwargs=None, callback=None):
        # todo: remove sync from api in abstract class
        raise NotImplementedError

    async def execute_generator(
            self, obj, gen, args=(), kwargs=None, callback=None
    ) -> AsyncGenerator:
        raise NotImplementedError

    @classmethod
    def call_execute_callback(cls, obj, return_value, callback):
        callback = cls.get_execute_callback_func(obj, callback)
        if callback is None:
            return

        callback(return_value)

    @classmethod
    def call_execute_callback_func(cls, return_value, callback):
        if callback is None:
            return

        callback(return_value)

    @classmethod
    def get_execute_callback_func(cls, obj, callback):
        if callback is NO_CALLBACK:
            return None
        if callback is None:
            return None

        if not isinstance(callback, str):
            callback = callback.__name__
        return getattr(obj, callback)

    async def get_echo_clock(self) -> Tuple[int, int, int]:
        raise NotImplementedError

    async def __aenter__(self):
        await self.start_executor()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop_executor()


def apply_executor(func=None, callback=None):
    """Decorator that calls the method using the executor.
    """
    if func is None:
        return partial(apply_executor, callback=callback)

    is_coro = iscoroutinefunction(func)

    if isgeneratorfunction(func) or isasyncgenfunction(func):
        raise ValueError(
            f'apply_executor called with generator function "{func}". '
            f'apply_executor does not support generators. Please use '
            f'apply_generator_executor instead')

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        executor: Executor = getattr(self, 'executor', None)
        if executor is None:
            ret_val = func(self, *args, **kwargs)
            Executor.call_execute_callback(self, ret_val, callback)
            return ret_val

        if not executor.supports_non_coroutine:
            raise ValueError(
                f'apply_executor called with normal function "{func}", but '
                f'Executor "{executor}" only supports async coroutines')
        return await executor.execute(self, func, args, kwargs, callback)

    @wraps(func)
    async def wrapper_coro(self, *args, **kwargs):
        executor: Executor = getattr(self, 'executor', None)
        if executor is None:
            ret_val = await func(self, *args, **kwargs)
            Executor.call_execute_callback(self, ret_val, callback)
            return ret_val

        if not executor.supports_coroutine:
            raise ValueError(
                f'apply_executor called with async coroutine "{func}", but '
                f'Executor "{executor}" does not support coroutines')
        return await executor.execute(self, func, args, kwargs, callback)

    if is_coro:
        return wrapper_coro
    return wrapper


def apply_generator_executor(func=None, callback=None):
    """Decorator that calls the generator method using the executor.
    """
    if func is None:
        return partial(apply_generator_executor, callback=callback)

    is_coro = iscoroutinefunction(func)

    if not isgeneratorfunction(func) and not isasyncgenfunction(func):
        raise ValueError(
            f'apply_generator_executor called with non-generator function '
            f'"{func}". apply_generator_executor only supports generators. '
            f'Please use apply_executor instead')

    @contextlib.asynccontextmanager
    @wraps(func)
    async def wrapper_gen(self, *args, **kwargs):
        executor: Executor = getattr(self, 'executor', None)
        if executor is None:
            async def eat_generator():
                callback_fn = Executor.get_execute_callback_func(
                    self, callback)
                call_callback = Executor.call_execute_callback_func

                for yield_val in func(self, *args, **kwargs):
                    call_callback(yield_val, callback_fn)
                    yield yield_val
                    await trio.sleep(0)

            gen = eat_generator()
        else:
            if not executor.supports_non_coroutine:
                raise ValueError(
                    f'apply_executor called with normal function "{func}", but '
                    f'Executor "{executor}" only supports async coroutines')

            gen = executor.execute_generator(
                self, func, args, kwargs, callback)

        async with aclosing(gen) as aiter:
            yield aiter

    @contextlib.asynccontextmanager
    @wraps(func)
    async def wrapper_coro_gen(self, *args, **kwargs):
        executor: Executor = getattr(self, 'executor', None)
        if executor is None:
            async def eat_generator():
                callback_fn = Executor.get_execute_callback_func(
                    self, callback)
                call_callback = Executor.call_execute_callback_func

                async for yield_val in func(self, *args, **kwargs):
                    call_callback(yield_val, callback_fn)
                    yield yield_val

            gen = eat_generator()
        else:
            if not executor.supports_coroutine:
                raise ValueError(
                    f'apply_executor called with async coroutine "{func}", but'
                    f' Executor "{executor}" does not support coroutines')

            gen = executor.execute_generator(
                self, func, args, kwargs, callback)

        async with aclosing(gen) as aiter:
            yield aiter

    if is_coro:
        return wrapper_coro_gen
    return wrapper_gen
