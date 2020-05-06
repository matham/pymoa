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

    _thread = None

    _exec_queue = None

    name = "ThreadExecutor"

    eof = object()

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
        thread = self._thread = threading.Thread(
            target=self._worker_thread_fn,  name=self.name,  daemon=True,
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

        self._thread = self._exec_queue = None

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
        await trio.hazmat.checkpoint_if_cancelled()
        self._exec_queue.put(
            (obj, sync_fn, args, kwargs or {}, trio.hazmat.current_task(),
             trio.hazmat.current_trio_token()))

        def abort(raise_cancel):
            # cannot be canceled
            return trio.hazmat.Abort.FAILED
        res = await trio.hazmat.wait_task_rescheduled(abort)

        if obj is not self.eof:
            self.call_execute_callback(obj, res, callback)
        return res


class AsyncThreadExecutor(Executor):

    supports_coroutine = True

    to_thread_portal: 'TrioPortal' = None

    _thread = None

    send_channel: trio.MemorySendChannel = None

    name = "AsyncThreadExecutor"

    eof = object()

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
        thread = self._thread = threading.Thread(
            target=self._worker_thread_fn,  name=self.name,  daemon=True,
            args=(event,))
        thread.start()
        # wait until class variables are set
        await event.wait()

    async def stop_executor(self, block=True):
        if not self._thread:
            return

        if not self.to_thread_portal or not self.send_channel:
            self._thread = None
            return

        await self.execute(self.eof, None)
        if block:
            self._thread.join()

        self._thread = None

    def _worker_thread_fn(self, event):
        # This is the function that runs in the worker thread to do the actual
        # work
        eof = self.eof

        async def runner():
            self.to_thread_portal = TrioPortal()
            self.send_channel, receive_channel = trio.open_memory_channel(
                math.inf)
            event.set()

            async for (obj, async_fn, args, kwargs, task, token
                       ) in receive_channel:
                if obj is eof:
                    try:
                        token.run_sync_soon(trio.hazmat.reschedule, task)
                    except trio.RunFinishedError:
                        pass
                    return

                result = await outcome.acapture(async_fn, obj, *args, **kwargs)
                try:
                    token.run_sync_soon(trio.hazmat.reschedule, task, result)
                except trio.RunFinishedError:
                    # The entire run finished, so our particular tasks are
                    # certainly long gone - it must have cancelled. Continue
                    # eating the queue.
                    pass

        trio.run(runner)

    @trio.hazmat.enable_ki_protection
    async def execute(
            self, obj, async_fn, args=(), kwargs=None, callback=None):
        '''It's guaranteed sequential. '''
        await trio.hazmat.checkpoint_if_cancelled()
        await self.to_thread_portal.run_sync(
            self.send_channel.send_nowait, (
                obj, async_fn, args, kwargs or {},
                trio.hazmat.current_task(), trio.hazmat.current_trio_token()
            )
        )

        def abort(raise_cancel):
            # cannot be canceled
            return trio.hazmat.Abort.FAILED
        res = await trio.hazmat.wait_task_rescheduled(abort)

        if obj is not self.eof:
            self.call_execute_callback(obj, res, callback)
        return res


class TrioPortal(object):

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
            (cb, fn, args, trio.hazmat.current_task(),
             trio.hazmat.current_trio_token()))

        def abort(raise_cancel):
            return trio.hazmat.Abort.FAILED
        return await trio.hazmat.wait_task_rescheduled(abort)

    async def run(self, afn, *args):
        return await self._do_it_async(self._run_cb_async, afn, args)

    async def run_sync(self, fn, *args):
        return await self._do_it_async(self._run_sync_cb_async, fn, args)
