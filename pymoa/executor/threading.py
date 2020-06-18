"""Threading
=============
"""

from typing import Tuple, AsyncGenerator
import threading
import math
import queue as stdlib_queue
from queue import Empty
import trio
import outcome
import time
import logging
from pymoa.utils import MaxSizeSkipDeque


from pymoa.executor import Executor, NO_CALLBACK


__all__ = ('ThreadExecutor', 'AsyncThreadExecutor', 'TrioPortal')


class ThreadExecutor(Executor):
    """Executor that executes functions in a secondary thread.
    """

    _thread = None

    _exec_queue = None

    name = "ThreadExecutor"

    eof = object()

    limiter: trio.CapacityLimiter = None

    max_queue_size = 10

    def __init__(self, name='ThreadExecutor', **kwargs):
        super(ThreadExecutor, self).__init__(**kwargs)
        self.name = name

    def __del__(self):
        if self._thread is not None:
            logging.warning(f'stop_executor was not called for "{self}"')

    async def start_executor(self):
        queue = self._exec_queue = stdlib_queue.Queue()
        # daemon=True because it might get left behind if we cancel, and in
        # this case shouldn't block process exit.
        self.limiter = trio.CapacityLimiter(1)
        thread = self._thread = threading.Thread(
            target=self._worker_thread_fn, name=self.name, daemon=True,
            args=(queue, ))
        thread.start()

    async def stop_executor(self, block=True):
        if not self._thread:
            return

        if not self._exec_queue:
            self._thread = None
            return

        await self.execute(self.eof, None, callback=NO_CALLBACK)
        if block:
            self._thread.join()

        self._thread = self._exec_queue = self.limiter = None

    def _worker_thread_fn(self, queue):
        # This is the function that runs in the worker thread to do the actual
        # work and then schedule the calls to report_back_in_trio_thread_fn
        eof = self.eof
        while True:
            obj, sync_fn, args, kwargs, task, token, gen_queue, gen_do_eof = \
                queue.get(block=True)

            if obj is eof:
                try:
                    token.run_sync_soon(trio.lowlevel.reschedule, task)
                except trio.RunFinishedError:
                    pass
                return

            if gen_queue is None:
                result = outcome.capture(sync_fn, obj, *args, **kwargs)
                try:
                    token.run_sync_soon(trio.lowlevel.reschedule, task, result)
                except trio.RunFinishedError:
                    # The entire run finished, so our particular tasks are
                    # certainly long gone - it must have cancelled. Continue
                    # eating the queue.
                    pass
            else:
                send_channel, std_queue = gen_queue

                def send_nowait():
                    try:
                        send_channel.send_nowait(None)
                    except trio.WouldBlock:
                        pass

                put = std_queue.put
                # we send to queue followed by ping on memory channel. We
                # cannot deadlock, because the ping will result in removing at
                # least one item, ensuring there will always be at least one
                # item space free eventually, so put will only block for a
                # short time until then. And then put will ping again
                result = outcome.capture(sync_fn, obj, *args, **kwargs)
                try:
                    if isinstance(result, outcome.Error):
                        put(result, block=True)
                        token.run_sync_soon(send_nowait)
                        continue

                    gen = result.unwrap()
                    while gen_do_eof[0] is not eof:
                        result = outcome.capture(next, gen)
                        if isinstance(result, outcome.Error):
                            if isinstance(result.error, StopIteration):
                                result = None

                            put(result, block=True)
                            token.run_sync_soon(send_nowait)
                            break

                        put(result, block=True)
                        token.run_sync_soon(send_nowait)
                except trio.RunFinishedError:
                    pass

    @trio.lowlevel.enable_ki_protection
    async def execute(self, obj, sync_fn, args=(), kwargs=None, callback=None):
        '''It's guaranteed sequential. '''
        async with self.limiter:
            await trio.lowlevel.checkpoint_if_cancelled()
            self._exec_queue.put(
                (obj, sync_fn, args, kwargs or {}, trio.lowlevel.current_task(),
                 trio.lowlevel.current_trio_token(), None, None))

            def abort(raise_cancel):
                # cannot be canceled
                return trio.lowlevel.Abort.FAILED
            res = await trio.lowlevel.wait_task_rescheduled(abort)

            if callback is not NO_CALLBACK:
                self.call_execute_callback(obj, res, callback)
        return res

    async def execute_generator(
            self, obj, sync_gen, args=(), kwargs=None, callback=None
    ) -> AsyncGenerator:
        send_channel, receive_channel = trio.open_memory_channel(1)
        # we use this queue for back-pressure
        queue = stdlib_queue.Queue(maxsize=max(self.max_queue_size, 2))
        callback = self.get_execute_callback_func(obj, callback)
        call_callback = self.call_execute_callback_func
        do_eof = [None]
        token = trio.lowlevel.current_trio_token()

        async with self.limiter:
            await trio.lowlevel.checkpoint_if_cancelled()

            self._exec_queue.put(
                (obj, sync_gen, args, kwargs or {}, None, token,
                 (send_channel, queue), do_eof))

            try:
                async for _ in receive_channel:
                    while True:
                        try:
                            result = queue.get(block=False)
                        except Empty:
                            break
                        if result is None:
                            return

                        result = result.unwrap()

                        call_callback(result, callback)
                        yield result
            finally:
                do_eof[0] = self.eof
                while True:
                    try:
                        queue.get(block=False)
                    except Empty:
                        break

    async def get_echo_clock(self) -> Tuple[int, int, int]:
        def get_time(*args):
            return time.perf_counter_ns()

        ts = time.perf_counter_ns()
        t = await self.execute(None, get_time, callback=NO_CALLBACK)
        return ts, t, time.perf_counter_ns()


class AsyncThreadExecutor(Executor):
    """Executor that executes async functions in a trio event loop in a
    secondary thread.
    """

    supports_coroutine = True

    supports_non_coroutine = False

    to_thread_portal: 'TrioPortal' = None

    _thread = None

    name = "AsyncThreadExecutor"

    limiter: trio.CapacityLimiter = None

    cancel_nursery: trio.Nursery = None

    def __init__(self, name='AsyncThreadExecutor', **kwargs):
        super(AsyncThreadExecutor, self).__init__(**kwargs)
        self.name = name

    def __del__(self):
        if self._thread is not None:
            logging.warning(f'stop_executor was not called for "{self}"')

    async def start_executor(self):
        # daemon=True because it might get left behind if we cancel, and in
        # this case shouldn't block process exit.
        event = trio.Event()
        from_thread_portal = TrioPortal()
        self.limiter = trio.CapacityLimiter(1)

        thread = self._thread = threading.Thread(
            target=self._worker_thread_fn, name=self.name, daemon=True,
            args=(event, from_thread_portal))
        thread.start()
        # wait until class variables are set
        await event.wait()

    async def stop_executor(self, block=True):
        if not self._thread:
            return

        # ideally start_executor cannot be canceled if thread still ran
        if not self.to_thread_portal or self.limiter is None or \
                self.cancel_nursery is None:
            self._thread = None
            return

        async def cancel(*args):
            self.cancel_nursery.cancel_scope.cancel()

        await self.execute(None, cancel, callback=NO_CALLBACK)
        if block:
            self._thread.join()

        self._thread = self.limiter = self.to_thread_portal = \
            self.cancel_nursery = None

    def _worker_thread_fn(self, event, from_thread_portal: 'TrioPortal'):
        # This is the function that runs in the worker thread to do the actual
        # work
        async def runner():
            async with trio.open_nursery() as nursery:
                self.to_thread_portal = TrioPortal()
                self.cancel_nursery = nursery
                await from_thread_portal.run_sync(event.set)

                await trio.sleep(math.inf)

        trio.run(runner)

    async def _execute_function(self, obj, async_fn, args, kwargs):
        return await async_fn(obj, *args, **kwargs)

    async def execute(
            self, obj, async_fn, args=(), kwargs=None, callback=None):
        async with self.limiter:
            res = await self.to_thread_portal.run(
                self._execute_function, obj, async_fn, args, kwargs or {})

            if callback is not NO_CALLBACK:
                self.call_execute_callback(obj, res, callback)
        return res

    async def execute_generator(
            self, obj, sync_gen, args=(), kwargs=None, callback=None
    ) -> AsyncGenerator:
        raise NotImplementedError

    async def get_echo_clock(self) -> Tuple[int, int, int]:
        async def get_time(*args):
            return time.perf_counter_ns()

        ts = time.perf_counter_ns()
        t = await self.execute(None, get_time, callback=NO_CALLBACK)
        return ts, t, time.perf_counter_ns()


class TrioPortal(object):
    """Portal for communicating with trio from a different thread.
    """

    trio_token: trio.lowlevel.TrioToken = None

    def __init__(self, trio_token=None):
        if trio_token is None:
            trio_token = trio.lowlevel.current_trio_token()
        self.trio_token = trio_token

    # This is the part that runs in the trio thread
    def _run_cb_async(self, afn, args, task, token):
        @trio.lowlevel.disable_ki_protection
        async def unprotected_afn():
            return await afn(*args)

        async def await_in_trio_thread_task():
            result = await outcome.acapture(unprotected_afn)
            try:
                token.run_sync_soon(trio.lowlevel.reschedule, task, result)
            except trio.RunFinishedError:
                # The entire run finished, so our particular tasks are certainly
                # long gone - it must have cancelled.
                pass

        trio.lowlevel.spawn_system_task(await_in_trio_thread_task, name=afn)

    def _run_sync_cb_async(self, fn, args, task, token):
        @trio.lowlevel.disable_ki_protection
        def unprotected_fn():
            return fn(*args)

        result = outcome.capture(unprotected_fn)
        try:
            token.run_sync_soon(trio.lowlevel.reschedule, task, result)
        except trio.RunFinishedError:
            # The entire run finished, so our particular tasks are certainly
            # long gone - it must have cancelled.
            pass

    @trio.lowlevel.enable_ki_protection
    async def _do_it_async(self, cb, fn, args):
        await trio.lowlevel.checkpoint_if_cancelled()
        self.trio_token.run_sync_soon(
            cb, fn, args, trio.lowlevel.current_task(),
            trio.lowlevel.current_trio_token())

        def abort(raise_cancel):
            return trio.lowlevel.Abort.FAILED
        return await trio.lowlevel.wait_task_rescheduled(abort)

    async def run(self, afn, *args):
        return await self._do_it_async(self._run_cb_async, afn, args)

    async def run_sync(self, fn, *args):
        return await self._do_it_async(self._run_sync_cb_async, fn, args)
