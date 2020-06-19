import trio
import outcome
import math
from functools import wraps, partial
from contextvars import ContextVar
from contextlib import contextmanager
from typing import Optional, Tuple, ContextManager, Generator, Callable
import time
from queue import Queue, Empty
from collections import deque
from asyncio import iscoroutinefunction

from kivy.clock import ClockBase, ClockNotRunningError, ClockEvent

from pymoa.executor.threading import TrioPortal

__all__ = (
    'EventLoopStoppedError', 'KivyEventCancelled', 'mark', 'async_run_in_kivy',
    'kivy_run_in_async', 'KivyCallbackEvent',
    'trio_context_manager', 'kivy_context_manager',
    'get_thread_context_managers', 'ContextVarContextManager',
    'TrioPortalContextManager', 'KivyClockContextManager',
    'AsyncKivyEventQueue', 'AsyncKivyBind')


class ContextVarContextManager:

    context_var = None

    value = None

    token = None

    def __init__(self, context_var, value=None):
        self.context_var = context_var
        self.value = value

    def __enter__(self):
        self.token = self.context_var.set(self.value)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.context_var.reset(self.token)
        self.token = None


class TrioPortalContextManager(ContextVarContextManager):

    def __init__(self, portal: TrioPortal):
        super(TrioPortalContextManager, self).__init__(trio_entry)
        self.value = portal


class KivyClockContextManager(ContextVarContextManager):

    def __init__(self, clock: ClockBase):
        super(KivyClockContextManager, self).__init__(kivy_clock)
        self.value = clock


kivy_clock = ContextVar('kivy_clock')
kivy_thread: ContextVar[Optional[ClockBase]] = ContextVar(
    'kivy_thread', default=None)
trio_entry: ContextVar[TrioPortal] = ContextVar('trio_entry')
trio_thread: ContextVar[Optional[TrioPortal]] = ContextVar(
    'trio_thread', default=None)


@contextmanager
def trio_context_manager(clock, queue):
    portal = TrioPortal()
    queue.put(portal)

    with KivyClockContextManager(clock):
        with ContextVarContextManager(trio_thread, portal):
            yield


@contextmanager
def kivy_context_manager(clock, queue):
    ts = time.perf_counter()
    res = None
    while time.perf_counter() - ts < 1:
        try:
            res = queue.get(block=True, timeout=.1)
        except Empty:
            pass
        else:
            break

    if res is None:
        raise TimeoutError(
            "Timed out waiting for trio thread to initialize. If there's only "
            "on thread, did you enter kivy_context_manager before "
            "trio_context_manager? With multiple threads, the trio thread "
            "should be started before entering kivy_context_manager to "
            "prevent deadlock of the kivy thread")

    with TrioPortalContextManager(res):
        with ContextVarContextManager(kivy_thread, clock):
            yield


def get_thread_context_managers():
    """Gets the context managers required to run kivy and trio threads.

    :return: tuple of kivy_context_manager, trio_context_manager
    """
    from kivy.clock import Clock
    queue = Queue(maxsize=1)

    return partial(kivy_context_manager, Clock, queue), \
        partial(trio_context_manager, Clock, queue)


class EventLoopStoppedError(Exception):
    pass


class KivyEventCancelled(BaseException):
    pass


def _report_kivy_back_in_trio_thread_fn(task_container, task):
    # This function gets scheduled into the trio run loop to deliver the
    # thread's result.
    # def do_release_then_return_result():
    #     # if canceled, do the cancellation otherwise the result.
    #     if task_container[0] is not None:
    #         task_container[0]()
    #     return task_container[1].unwrap()
    # result = outcome.capture(do_release_then_return_result)

    # currently this is only called when kivy callback was called/not canceled
    trio.lowlevel.reschedule(task, task_container[1])


def async_run_in_kivy(func=None):
    # if it's canceled in the async side, it either succeeds if we cancel on
    # kivy side or waits until kivy calls us back. If Kivy stops early it still
    # processes the callback so it's fine. So it either raises a
    # EventLoopStoppedError immediately or fails
    if func is None:
        return partial(async_run_in_kivy)

    if iscoroutinefunction(func):
        raise ValueError(
            f'run_in_kivy called with async coroutine "{func}", but '
            f'run_in_kivy does not support coroutines (only sync functions)')

    @trio.lowlevel.enable_ki_protection
    @wraps(func)
    async def inner_func(*args, **kwargs):
        """When canceled, executed work is discarded. Thread safe.
        """
        clock: ClockBase = kivy_clock.get()
        lock = {}

        if kivy_thread.get() is clock:
            await trio.lowlevel.checkpoint_if_cancelled()
            # behavior should be the same whether it's in kivy's thread
            if clock.has_ended:
                raise EventLoopStoppedError(
                    f'async_run_in_kivy failed to complete <{func}> because '
                    f'clock stopped')
            return func(*args, **kwargs)

        task = trio.lowlevel.current_task()
        token = trio.lowlevel.current_trio_token()
        # items are: cancellation callback, the outcome, whether it was either
        # canceled or callback is already executing. Currently we don't handle
        # cancellation callback because it either succeeds in canceling
        # immediately or we get the kivy result
        task_container = [None, None, False]

        def kivy_thread_callback(*largs):
            # This is the function that runs in the worker thread to do the
            # actual work and then schedule the calls to report back to trio
            # are we handling the callback?
            lock.setdefault(None, 0)
            # it was canceled so we have nothing to do
            if lock[None] is None:
                return

            task_container[1] = outcome.capture(func, *args, **kwargs)

            # this may raise a RunFinishedError, but
            # The entire run finished, so our particular tasks are
            # certainly long gone - this shouldn't have happened because
            # either the task should still be waiting because it wasn't
            # canceled or if it was canceled we should have returned above
            token.run_sync_soon(
                _report_kivy_back_in_trio_thread_fn, task_container, task)

        def kivy_thread_callback_stopped(*largs):
            # This is the function that runs in the worker thread to do the
            # actual work and then schedule the calls to report back to trio
            # are we handling the callback?
            lock.setdefault(None, 0)
            # it was canceled so we have nothing to do
            if lock[None] is None:
                return

            def raise_stopped_error():
                raise EventLoopStoppedError(
                    f'async_run_in_kivy failed to complete <{func}> because '
                    f'clock stopped')

            task_container[1] = outcome.capture(raise_stopped_error)
            token.run_sync_soon(
                _report_kivy_back_in_trio_thread_fn, task_container, task)

        trigger = clock.create_lifecycle_aware_trigger(
            kivy_thread_callback, kivy_thread_callback_stopped,
            release_ref=False)
        try:
            trigger()
        except ClockNotRunningError as e:
            raise EventLoopStoppedError(
                f'async_run_in_kivy failed to complete <{func}>') from e
        # kivy_thread_callback will be called, unless canceled below

        def abort(raise_cancel):
            # task_container[0] = raise_cancel

            # try canceling
            trigger.cancel()
            lock.setdefault(None, None)
            # it is canceled, kivy shouldn't handle it
            if lock[None] is None:
                return trio.lowlevel.Abort.SUCCEEDED
            # it was already started so we can't cancel - wait for result
            return trio.lowlevel.Abort.FAILED

        return await trio.lowlevel.wait_task_rescheduled(abort)

    return inner_func


def mark(__func, *args, **kwargs):
    return __func, args, kwargs


def _callback_raise_exception(*args):
    raise TypeError('Should never have timed out infinite wait')


def _do_nothing(*args):
    pass


class KivyCallbackEvent:

    __slots__ = 'gen', 'clock', 'orig_func', 'clock_event'

    gen: Optional[Generator]

    clock: ClockBase

    orig_func: Callable

    clock_event: Optional[ClockEvent]

    def __init__(self, clock: ClockBase, func, gen, ret_func):
        super().__init__()
        self.clock = clock
        self.orig_func = func

        # if kivy stops before we finished processing gen, cancel it
        self.gen = gen
        event = self.clock_event = clock.create_lifecycle_aware_trigger(
            _callback_raise_exception, self._cancel, timeout=math.inf,
            release_ref=False)

        try:
            event()

            portal = trio_entry.get()
            if trio_thread.get() is portal:
                trio.lowlevel.spawn_system_task(
                    self._async_callback, *ret_func)
            else:
                portal.trio_token.run_sync_soon(self._spawn_task, ret_func)
        except BaseException as e:
            self._cancel(e=e)

    def cancel(self, *args):
        """Only safe from kivy thread.
        """
        self._cancel(suppress_cancel=True)

    def _cancel(self, *args, e=None, suppress_cancel=False):
        if self.gen is None:
            return

        if e is None:
            e = KivyEventCancelled

        self.clock_event.cancel()
        self.clock_event = None

        try:
            self.gen.throw(e)
        except StopIteration:
            # generator is done
            pass
        except KivyEventCancelled:
            # it is canceled
            if not suppress_cancel:
                raise
        finally:
            # can't cancel again
            self.gen = None

    def _spawn_task(self, ret_func):
        try:
            trio.lowlevel.spawn_system_task(self._async_callback, *ret_func)
        except BaseException as e:
            event = self.clock.create_lifecycle_aware_trigger(
                partial(self._cancel, e=e), _do_nothing, release_ref=False)
            try:
                event()
            except ClockNotRunningError:
                pass

    def _kivy_callback(self, result, *args):
        # check if canceled
        if self.gen is None:
            return

        try:
            result.send(self.gen)
        except StopIteration:
            pass
        else:
            raise RuntimeError(
                f'{self.orig_func} does not return after the first yield. '
                f'Does it maybe have more than one yield? Only one yield '
                f'statement is supported')
        finally:
            self.clock_event.cancel()
            self.clock_event = None
            self.gen = None

    async def _async_callback(self, ret_func, ret_args=(), ret_kwargs=None):
        # check if canceled
        if self.gen is None:
            return

        if iscoroutinefunction(ret_func):
            with trio.CancelScope(shield=True):
                # TODO: cancel this when event is cancelled
                result = await outcome.acapture(
                    ret_func, *ret_args, **(ret_kwargs or {}))

            assert not (hasattr(result, 'error') and
                        isinstance(result.error, trio.Cancelled))
        else:
            result = outcome.capture(ret_func, *ret_args, **(ret_kwargs or {}))

        # check if canceled
        if self.gen is None:
            return

        event = self.clock.create_lifecycle_aware_trigger(
            partial(self._kivy_callback, result), _do_nothing,
            release_ref=False)
        try:
            event()
        except ClockNotRunningError:
            pass


def kivy_run_in_async(func):
    """May be raised from other threads.
    """
    @wraps(func)
    def run_to_yield(*args, **kwargs):
        from kivy.clock import Clock

        gen = func(*args, **kwargs)
        try:
            ret_func = next(gen)
        except StopIteration:
            return None

        return KivyCallbackEvent(Clock, func, gen, ret_func)

    return run_to_yield


class AsyncKivyEventQueue:
    """A class for asynchronously iterating values in a queue and waiting
    for the queue to be updated with new values through a callback function.

    An instance is an async iterator which for every iteration waits for
    callbacks to add values to the queue and then returns it.

    :Parameters:

        `filter`: callable or None
            A callable that is called with :meth:`callback`'s positional
            arguments. When provided, if it returns false, this call is dropped.
        `convert`: callable or None
            A callable that is called with :meth:`callback`'s positional
            arguments. It is called immediately as opposed to async.
            If provided, the return value of convert is returned by
            the iterator rather than the original value. Helpful
            for callback values that need to be processed immediately.
        `max_len`: int or None
            If None, the callback queue may grow to an arbitrary length.
            Otherwise, it is bounded to maxlen. Once it's full, when new items
            are added a corresponding number of oldest items are discarded.
        `thread_fn`: callable or None
            If reading from the queue is done with a different thread than
            writing it, this is the callback that schedules in the read thread.
    """

    _quit: bool = False

    send_channel: Optional[trio.MemorySendChannel] = None

    receive_channel: [trio.MemoryReceiveChannel] = None

    queue: Optional[deque] = None

    filter: Optional[Callable] = None

    convert: Optional[Callable] = None

    _max_len = None

    def __init__(
            self, filter_fn: Optional[Callable] = None,
            convert: Optional[Callable] = None, max_len: Optional[int] = None,
            **kwargs):
        super().__init__(**kwargs)
        self.filter = filter_fn
        self.convert = convert
        self._max_len = max_len

    async def __aenter__(self):
        if self.queue is not None:
            raise TypeError('Cannot re-enter because it was not properly '
                            'cleaned up on the last exit')

        self.queue = deque(maxlen=self._max_len)
        self.send_channel, self.receive_channel = trio.open_memory_channel(1)
        self._quit = False

        await async_run_in_kivy(self.start_callback)()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._quit = True
        self.send_channel = self.receive_channel = None
        await async_run_in_kivy(self.stop_callback)()
        self.queue = None  # this lets us detect if stop raised an error

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.send_channel is None:
            raise TypeError('Can only iterate when context was entered')

        while not self.queue:
            await self.receive_channel.receive()

        return self.queue.popleft()

    def add_item(self, *args):
        """This (and only this) function may be executed from another thread
        because the callback may be bound to code executing from an external
        thread.
        """
        f = self.filter
        if self._quit or f is not None and not f(*args):
            return

        convert = self.convert
        if convert is not None:
            args = convert(*args)

        queue = self.queue
        if queue is None:
            return
        queue.append(args)

        portal = trio_entry.get()
        if trio_thread.get() is portal:
            # same thread
            self._send_on_channel()
        else:
            portal.trio_token.run_sync_soon(self._send_on_channel)

    def _send_on_channel(self):
        send_channel = self.send_channel
        if send_channel is not None:
            try:
                send_channel.send_nowait(None)
            except trio.WouldBlock:
                pass

    def start_callback(self):
        pass

    def stop_callback(self):
        pass


class AsyncKivyBind(AsyncKivyEventQueue):
    """A class for asynchronously observing kivy properties and events.
    Creates an async iterator which for every iteration waits and
    returns the property or event value for every time the property changes
    or the event is dispatched.
    The returned value is identical to the list of values passed to a function
    bound to the event or property with bind. So at minimum it's a one element
    (for events) or two element (for properties, instance and value) list.
    :Parameters:
        `bound_obj`: :class:`EventDispatcher`
            The :class:`EventDispatcher` instance that contains the property
            or event being observed.
        `bound_name`: str
            The property or event name to observe.
        `current`: bool
            Whether the iterator should return the current value on its
            first class (True) or wait for the first event/property dispatch
            before having a value (False). Defaults to True.
            Only if it's a property and not an event.
    E.g.::
        async for x, y in AsyncBindQueue(
            bound_obj=widget, bound_name='size', convert=lambda x: x[1]):
            print(value)
    Or::
        async for touch in AsyncBindQueue(
            bound_obj=widget, bound_name='on_touch_down',
            convert=lambda x: x[0]):
            print(value)
    """

    bound_obj = None

    bound_name = ''

    bound_uid = 0

    current = True

    def __init__(self, bound_obj, bound_name, current=True, **kwargs):
        super().__init__(**kwargs)
        self.bound_name = bound_name
        self.bound_obj = bound_obj
        self.current = current

    def start_callback(self):
        super().start_callback()
        bound_obj = self.bound_obj
        bound_name = self.bound_name

        uid = self.bound_uid = bound_obj.fbind(bound_name, self.add_item)
        if not uid:
            raise ValueError(
                '{} is not a recognized property or event of {}'
                ''.format(bound_name, bound_obj))

        if self.current and not bound_obj.is_event_type(bound_name):
            self.add_item(bound_obj, getattr(bound_obj, bound_name))

    def stop_callback(self):
        super().stop_callback()

        if self.bound_uid:
            self.bound_obj.unbind_uid(self.bound_name, self.bound_uid)
            self.bound_uid = 0
            self.bound_obj = None
