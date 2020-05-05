"""Utilities
===============

Module that provides helpful classes and functions.
"""
from typing import Optional, Callable
from collections import deque
from queue import Full
import trio
import math

__all__ = (
    'get_class_bases', 'async_zip', 'AsyncCallbackQueue', 'MaxSizeSkipDeque')


def get_class_bases(cls):
    for base in cls.__bases__:
        if base.__name__ == 'object':
            break
        for cbase in get_class_bases(base):
            yield cbase
        yield base


class async_zip(object):

    def __init__(self, *largs):
        self.aiterators = [obj.__aiter__() for obj in largs]
        self.items = [None, ] * len(largs)
        self.done = False

    async def _accumulate(self, aiterator, i):
        try:
            self.items[i] = await aiterator.__next__()
        except StopAsyncIteration:
            self.done = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.done:
            raise StopAsyncIteration

        async with trio.open_nursery() as nursery:
            for i, aiterator in enumerate(self.aiterators):
                nursery.start_soon(self._accumulate, aiterator, i)

        if self.done:
            raise StopAsyncIteration
        return tuple(self.items)


class AsyncCallbackQueue(object):
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
        `maxlen`: int or None
            If None, the callback queue may grow to an arbitrary length.
            Otherwise, it is bounded to maxlen. Once it's full, when new items
            are added a corresponding number of oldest items are discarded.
        `thread_fn`: callable or None
            If reading from the queue is done with a different thread than
            writing it, this is the callback that schedules in the read thread.
    """

    # todo: switch to trio memory channels

    _quit: bool = False

    def __init__(
            self, filter_fn: Optional[Callable] = None,
            convert: Optional[Callable] = None, maxlen: Optional[int] = None,
            thread_fn: Optional[Callable] = None, **kwargs):
        super(AsyncCallbackQueue, self).__init__(**kwargs)
        self.filter = filter_fn
        self.convert = convert
        self.callback_result = deque(maxlen=maxlen)
        self.thread_fn = thread_fn
        self.event = trio.Event()

    def __del__(self):
        self.stop()

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._quit:
            raise StopAsyncIteration

        self.event.clear()
        while not self.callback_result:
            await self.event.wait()
            self.event.clear()

        if self.callback_result:
            return self.callback_result.popleft()

        self.stop()
        raise StopAsyncIteration

    def _thread_reentry(self, *largs, **kwargs):
        self.event.set()

    def callback(self, *args):
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

        self.callback_result.append(args)

        thread_fn = self.thread_fn
        if thread_fn is None:
            self.event.set()
        else:
            thread_fn(self._thread_reentry)

    def stop(self):
        """Stops the iterator and cleans up.
        """
        self._quit = True
        self.event.set()


class MaxSizeSkipDeque:

    send_channel: trio.MemorySendChannel = None

    receive_channel: trio.MemoryReceiveChannel = None

    size: int = 0

    packet: int = 0

    max_size = 0

    def __init__(self, max_size=0, **kwargs):
        super(MaxSizeSkipDeque, self).__init__(**kwargs)
        self.send_channel, self.receive_channel = trio.open_memory_channel(
            math.inf)
        self.max_size = max_size

    def __aiter__(self):
        return self

    async def __anext__(self):
        item, packet, size = await self.receive_channel.receive()
        self.size -= size
        return item, packet

    def add_item(self, item, size=1):
        if self.max_size and self.size + size > self.max_size:
            self.packet += 1
            raise Full

        self.size += size
        self.packet += 1
        self.send_channel.send_nowait((item, self.packet, size))
