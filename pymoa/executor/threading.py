"""Threading
=============
"""

from typing import Tuple
import threading
import math
import queue as stdlib_queue
import trio
import outcome
import time
import logging


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
            obj, sync_fn, args, kwargs, task, token = queue.get(
                block=True)
            if obj is eof:
                try:
                    token.run_sync_soon(trio.hazmat.reschedule, task)
                except trio.RunFinishedError:
                    pass
                return

            result = outcome.capture(sync_fn, obj, *args, **kwargs)
            try:
                token.run_sync_soon(trio.hazmat.reschedule, task, result)
            except trio.RunFinishedError:
                # The entire run finished, so our particular tasks are
                # certainly long gone - it must have cancelled. Continue
                # eating the queue.
                pass

    @trio.hazmat.enable_ki_protection
    async def execute(self, obj, sync_fn, args=(), kwargs=None, callback=None):
        '''It's guaranteed sequential. '''
        async with self.limiter:
            await trio.hazmat.checkpoint_if_cancelled()
            self._exec_queue.put(
                (obj, sync_fn, args, kwargs or {}, trio.hazmat.current_task(),
                 trio.hazmat.current_trio_token()))

            def abort(raise_cancel):
                # cannot be canceled
                return trio.hazmat.Abort.FAILED
            res = await trio.hazmat.wait_task_rescheduled(abort)

            if callback is not NO_CALLBACK:
                self.call_execute_callback(obj, res, callback)
        return res

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

    async def get_echo_clock(self) -> Tuple[int, int, int]:
        async def get_time(*args):
            return time.perf_counter_ns()

        ts = time.perf_counter_ns()
        t = await self.execute(None, get_time, callback=NO_CALLBACK)
        return ts, t, time.perf_counter_ns()


class TrioPortal(object):
    """Portal for communicating with trio from a different thread.
    """

    def __init__(self, trio_token=None):
        if trio_token is None:
            trio_token = trio.hazmat.current_trio_token()
        self._trio_token = trio_token

    # This is the part that runs in the trio thread
    def _run_cb_async(self, afn, args, task, token):
        @trio.hazmat.disable_ki_protection
        async def unprotected_afn():
            return await afn(*args)

        async def await_in_trio_thread_task():
            result = await outcome.acapture(unprotected_afn)
            try:
                token.run_sync_soon(trio.hazmat.reschedule, task, result)
            except trio.RunFinishedError:
                # The entire run finished, so our particular tasks are certainly
                # long gone - it must have cancelled.
                pass

        trio.hazmat.spawn_system_task(await_in_trio_thread_task, name=afn)

    def _run_sync_cb_async(self, fn, args, task, token):
        @trio.hazmat.disable_ki_protection
        def unprotected_fn():
            return fn(*args)

        result = outcome.capture(unprotected_fn)
        try:
            token.run_sync_soon(trio.hazmat.reschedule, task, result)
        except trio.RunFinishedError:
            # The entire run finished, so our particular tasks are certainly
            # long gone - it must have cancelled.
            pass

    @trio.hazmat.enable_ki_protection
    async def _do_it_async(self, cb, fn, args):
        await trio.hazmat.checkpoint_if_cancelled()
        self._trio_token.run_sync_soon(
            cb, fn, args, trio.hazmat.current_task(),
            trio.hazmat.current_trio_token())

        def abort(raise_cancel):
            return trio.hazmat.Abort.FAILED
        return await trio.hazmat.wait_task_rescheduled(abort)

    async def run(self, afn, *args):
        return await self._do_it_async(self._run_cb_async, afn, args)

    async def run_sync(self, fn, *args):
        return await self._do_it_async(self._run_sync_cb_async, fn, args)
