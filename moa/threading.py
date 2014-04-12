from __future__ import absolute_import


__all__ = ('CallbackQueue', )

import inspect
from threading import RLock
try:
    from Queue import Queue
except ImportError:
    from queue import Queue
from collections import deque


class CallbackDeque(deque):
    '''
    A Multithread safe class that calls a callback whenever an item is added
    to the queue. Instead of having to poll or wait, you could wait to get
    notified of additions.


    :Parameters:
        `callback`: callable
            The function to call when adding to the queue
    '''

    callback = None

    def __init__(self, callback, **kwargs):
        deque.__init__(self, **kwargs)
        self.callback = callback

    def append(self, x, *largs, **kwargs):
        deque.append(self, (x, largs, kwargs))
        self.callback()

    def appendleft(self, x, *largs, **kwargs):
        deque.appendleft(self, (x, largs, kwargs))
        self.callback()


class CallbackQueue(Queue):
    '''
    A Multithread safe class that calls a callback whenever an item is added
    to the queue. Instead of having to poll or wait, you could wait to get
    notified of additions.

    >>> def callabck():
    ...     print('Added')
    >>> q = KivyQueue(notify_func=callabck)
    >>> q.put('test', 55)
    Added
    >>> q.get()
    ('test', 55)

    :Parameters:
        `notify_func`: callable
            The function to call when adding to the queue
    '''

    notify_func = None

    def __init__(self, notify_func, **kwargs):
        Queue.__init__(self, **kwargs)
        self.notify_func = notify_func

    def put(self, key, val):
        '''
        Adds a (key, value) tuple to the queue and calls the callback function.
        '''
        Queue.put(self, (key, val), False)
        self.notify_func()

    def get(self):
        '''
        Returns the next items in the queue, if non-empty, otherwise a
        :py:attr:`Queue.Empty` exception is raised.
        '''
        return Queue.get(self, False)


class ThreadExec(object):

    _exec_queue = None
    _schedule_lock = None
    _schedule = None
    _thread = None

    def __init__(self, allow_async=True, **kwargs):
        super(ThreadExec, self).__init__(**kwargs)

        if allow_async:
            self._exec_queue = Queue()
            self._schedule_lock = RLock()
            self._schedule = {}

    def __del__(self):
        pass

    def _thread_exec(self):
        pass

    def schedule(self, name, callback, **kwargs):
        func = getattr(self, name)
        if '_external' not in inspect.getargspec(func).args:
            raise Exception('')

    def schedule_repeated(self, name, callback, **kwargs):
        pass

    def unschedule_repeated(self, name, callback):
        pass
