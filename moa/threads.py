'''Threading module.
'''

from __future__ import absolute_import

__all__ = ('CallbackDeque', 'CallbackQueue', 'ScheduledEventLoop')

from collections import defaultdict, deque
from threading import RLock, Event, Thread
import traceback
try:
    from Queue import Queue
except ImportError:
    from queue import Queue
import sys

from moa.clock import Clock


class CallbackDeque(deque):
    '''
    A multithreading safe class that calls a callback whenever an item is
    appended to the :py:attr:`deque`. Instead of having to poll or wait, you
    could wait to get notified of additions.

    :Parameters:
        `callback`: callable
            The function to call when adding to the queue

    .. note::
        Only :meth:`append` and :meth:`appendleft` are currently implemented.

    ::

        >>> def callback():
        ...     print('Added')
        >>> dq = CallbackDeque(callback=callback)
        >>> dq.append('apples', 'caramel', nuts=True)
        Added
        >>> dq.pop()
        ('apples', ('caramel',), {'nuts': True})
    '''

    callback = None

    def __init__(self, callback, **kwargs):
        super(CallbackDeque, self).__init__(**kwargs)
        self.callback = callback

    def append(self, x, *largs, **kwargs):
        '''Appends `x`, and the positional and keyword args as a 3-tuple to the
        queue.
        '''
        super(CallbackDeque, self).append((x, largs, kwargs))
        self.callback()

    def appendleft(self, x, *largs, **kwargs):
        '''Appends `x`, and the positional and keyword args as a 3-tuple to the
        left of the queue.
        '''
        super(CallbackDeque, self).appendleft((x, largs, kwargs))
        self.callback()


class CallbackQueue(Queue):
    '''A multithreading safe class that calls a callback whenever an item is
    placed on the :py:attr:`Queue`. Instead of having to poll or wait, you
    could wait to get notified of additions.

    The class is helpful for passing massages between the kivy thread and
    other threads.

    :Parameters:
        `callback`: callable
            The function to call when adding to the queue

    .. note::
        Only :meth:`put` and :meth:`get` are currently implemented.

    ::

        >>> def callabck():
        ...     print('Added')
        >>> q = KivyQueue(callabck=callabck)
        >>> q.put('test', 55)
        Added
        >>> q.get()
        ('test', 55)
    '''

    callback = None

    def __init__(self, callback, **kwargs):
        super(CallbackQueue, self).__init__(**kwargs)
        self.callback = callback

    def put(self, key, val):
        '''Adds the (key, value) tuple to the queue and calls the callback
        function. The call is non-blocking.
        '''
        super(CallbackQueue, self).put((key, val), False)
        self.callback()

    def get(self):
        '''Returns the next tuple item in the queue, if non-empty, otherwise a
        :py:attr:`Queue.Empty` exception is raised.

        The call is non-blocking.
        '''
        return super(CallbackQueue, self).get(False)


class ScheduledEvent(object):
    '''An internal class used and returned when scheduling an event with
    :meth:`ScheduledEventLoop.request_callback`.
    '''

    repeat = False
    '''Whether the event is a one time shot, or repeats until removed.
    Applies whether :attr:`trigger` is True or False.
    '''
    func_kwargs = {}
    '''The kw args passed to the :attr:`name` function. '''
    callback = None
    '''The callback function to be executed from the kivy event loop after
    the scheduled method has been executed. '''
    scheduled_callbacks = []
    '''List of callbacks for this event scheduled to be executed by the kivy
    thread. These notify the original scheduler that the event completed.

    The elements in the list are 2-tuples of the result of the execution of
    :attr:`name`, followed by the :class:`ScheduledEvent` that caused the
    execution.
    '''
    trigger = True
    '''Whether this event is a trigger event. With `trigger` True the event is
    a normal event. If :attr:`trigger` is False, then the event will not
    execute on its own, but will listen to other events associated with
    the same method. That is, it will get callbacks for every execution of
    the method :attr:`name`.

    Also, if `trigger` is False, :attr:`callback` will get a keyword argument
    called event, which is the instance of this class that caused the callback.
    '''
    cls_method = True
    '''If this callback is to be executed for method :attr:`name` belonging to
    to :class:`ScheduledEventLoop` (True), or to
    :meth:`ScheduledEventLoop.target` (False).
    '''
    name = ''
    '''The name of the method associated with this event. See
    :meth:`ScheduledEventLoop.request_callback`.
    '''

    def __init__(self, callback=None, func_kwargs={}, repeat=False,
                 trigger=False, cls_method=True, name=''):
        self.callback = callback
        self.func_kwargs = func_kwargs
        self.repeat = repeat
        self.scheduled_callbacks = []
        self.trigger = trigger
        self.cls_method = cls_method
        self.name = name


class ScheduledEventLoop(object):
    '''This class provides a scheduling mechanism though which methods of this
    class or a object associated with this class (:attr:`target`) are executed
    from an internal thread. This eases execution of methods outside the
    main system thread. After execution, if set, the main
    thread executes a callback using the execution results.

    The class is meant to be used with a main thread, e.g. the kivy thread
    such that the a thread adds a new method to be executed. After the method
    is executed, the main thread receives the results of the execution and
    calls a callback with the results.

    :Parameters:

        `target`: object
            See :attr:`target`
        `daemon`: bool
            See :attr:`_daemon`. Defaults to False.
        `cls_method`: bool
            See :attr:`cls_method`. Defaults to True.

    For example::

        from moa.threads import ScheduledEventLoop
        from kivy.app import runTouchApp
        from kivy.uix.widget import Widget


        class Example(ScheduledEventLoop):

            def say_cheese(self, **kwargs):
                print('cheese from internal thread', kwargs)
                return 'cheese'

            def cry_cheese(self, **kwargs):
                raise Exception('Out of cheese')

            def handle_exception(self, exception, event):
                e, trace = exception
                print('got exception "{}" for event with name "{}" and kwargs "{}"'.
                      format(e, event.name, event.func_kwargs))
                # exit thread
                return False


        def example_callback(result):
            print('Result: {}'.format(result))

        example = Example()
        example.request_callback('say_cheese', example_callback, apple='gala',
                                 spice='cinnamon')

        example2 = Example()
        example2.request_callback('cry_cheese', example_callback, apple='gala',
                                  spice='cinnamon')

        runTouchApp(Widget())
        example.stop_thread(True)
        example2.stop_thread(True)

    When run, this prints::

        ('cheese from internal thread', {'apple': 'gala', 'spice': 'cinnamon'})
        got exception "Out of cheese" for event with name "cry_cheese" and \
kwargs "{'apple': 'gala', 'spice': 'cinnamon'}"
        Result: cheese

    .. note::
        We need to run a kiv app, otherwise the kivy thread won't execute any
        callbacks (i.e. `example_callback`).

        Also note, that if we don't explicitly stop the thread, the interpreter
        will not exit since the internal thread is not a daemon.
    '''

    __callback_lock = None
    '''Protects adding/removing callbacks. '''
    __thread_event = None
    ''' Signals exec thread that a new callback has been requested. '''
    __thread = None
    ''' Thread object. '''
    __signal_exit = False
    ''' Whether the thread should stop executing. '''
    __callbacks = None
    ''' Dict of the callbacks. '''
    __callbacks = None
    ''' Dict of the callbacks. '''
    _kivy_trigger = None
    '''A kivy Clock trigger telling the kivy thread to execute the callbacks.
    '''
    _daemon = False
    '''Whether the internal thread is a daemon thread.
    '''
    target = None
    '''An object, the methods of which will be executed in the internal thread.
    :meth:`request_callback` requests a method to be executed. The method
    can be a method of a class co-inherited from :class:`ScheduledEventLoop`,
    or a method of the object in target.
    '''
    cls_method = True
    '''If a callback scheduled with :meth:`request_callback` when `cls_method`
    is None is to be executed for :meth:`request_callback` parameter `name`
    belonging to to :class:`ScheduledEventLoop` (True), or to
    :meth:`ScheduledEventLoop.target` (False).
    '''

    def __init__(self, target=None, daemon=False, cls_method=True,
                 **kwargs):
        super(ScheduledEventLoop, self).__init__(**kwargs)
        self._daemon = daemon
        self.cls_method = cls_method
        self.__callback_lock = RLock()
        self.__thread_event = Event()
        self.__callbacks = defaultdict(list)
        self._kivy_trigger = Clock.create_trigger_priority(
            self._service_main_thread)
        self.target = target
        self.start_thread()

    def clear_events(self):
        '''Removes all the events. Similar to calling :meth:`remove_request`
        for all the events.

        .. warning::
            This method is only safe to be called when the internal thread is
            stopped (e.g. with :meth:`stop_thread`).
        '''
        cbs = self.__callbacks
        for key in cbs.keys():
            del cbs[key][:]
        self.__callbacks.clear()

    def start_thread(self):
        '''Starts a new instance of the internal thread. If the thread is
        already running, a new thread is NOT created.

        It does not modify any callbacks.

        This method is not multi-threading safe with :meth:`stop_thread`, so
        it should only be called from the main kivy thread.
        '''
        if self.__thread  is not None:
            return
        self.__signal_exit = False
        self.__thread_event.set()
        self.__thread = Thread(
            target=self._callback_thread, name='ScheduledEventLoop')
        self.__thread.daemon = self._daemon
        self.__thread.start()

    def stop_thread(self, join=False):
        '''Stops the internal thread. It does not modify any callbacks.

        This method is not multi-threading safe with :meth:`start_thread`, so
        it should only be called from the main kivy thread.

        :Parameters:

            `join`: bool
                If True, the calling thread will join the thread until it
                exits.
        '''
        self.__signal_exit = True
        self.__thread_event.set()
        thread = self.__thread
        if join and thread is not None:
            thread.join()

    def handle_exception(self, exception, event):
        ''' Called from the internal thread when the method executed within the
        thread raised an exception.

        :Parameters:

            `exception`: 2-tuple
                tuple of the Exception and `sys.exc_info()`.
            `event`: :class:`ScheduledEvent`
                The event that caused the exception. None if the error is not
                associated with an event.

        :Returns:
            If the return value evaluates to True, we attempt to
            execute the event's method again from the internal thread. If it
            evaluates to False, the internal thread exits.
        '''
        pass

    def request_callback(self, name, callback=None, trigger=True,
                         repeat=False, cls_method=None, **kwargs):
        '''Adds a callback to be executed by the internal thread.
        See :class:`ScheduledEvent`.

        :Parameters:

            `name`: str
                The name of the class or :attr:`target` method which will
                be executed from the internal thread. See :attr:`target` and
                :attr:`ScheduledEvent.name`
            `callback`: object
                A callback function which will be called by the main (kivy)
                thread with the results of the method `name` as executed by
                the internal thread. If `trigger` is False, the method will
                get a keyword argument `event`, which is the instance of
                :class:`ScheduledEvent` that caused the callback.

                If None, no callback will be called.
            `trigger`: bool
                See :attr:`ScheduledEvent.trigger`.
            `repeat`: bool
                See :attr:`ScheduledEvent.repeat`.
            `cls_method`: bool or None
                See :attr:`ScheduledEvent.cls_method`. As opposed to
                :attr:`ScheduledEvent.cls_method`, this parameter can also be
                None, in which case :attr:`cls_method` will be used
                instead. It defaults to None.
            `**kwargs`:
                The caught keyword arguments that will be passed to the method
                `name`. See :attr:`ScheduledEvent.func_kwargs`.

        :Returns:
            A instance of :class:`ScheduledEvent`.

        .. note::
            The order with which :meth:`request_callback` is called is not
            necessarily the order in which the internal thread will execute
            them.
        '''
        if cls_method is None:
            cls_method = self.cls_method
        ev = ScheduledEvent(
            callback=callback, func_kwargs=kwargs, repeat=repeat,
            trigger=trigger, cls_method=cls_method, name=name)
        with self.__callback_lock:
            self.__callbacks[name].append(ev)
        if trigger:
            self.__thread_event.set()
        return ev

    def remove_request(self, name, event):
        '''Unschedule a callback previously scheduled with
        :meth:`request_callback`.

        Due to threading uncertainty, it may still execute if the callback was
        the next event scheduled to be executed by the internal thread.

        :Parameters:

            `name`: str
                The name of the method. This should be the same as the `name`
                used in :meth:`request_callback`.
            `event`: :class:`ScheduledEvent`
                The scheduled event returned by :meth:`request_callback`.
        '''
        try:
            self.__callbacks[name].remove(event)
        except ValueError:
            pass

    def _schedule_thread_callbacks(
            self, name, event, result, callbacks):
        '''Called by the internal thread to schedule callbacks by the main
        thread using the results of an execution of method `name`.

        :Parameters:

            `name`: str
                The name of the method executed.
            `event`: :class:`ScheduledEvent`
                The event that caused the execution of `name`.
            `result`:
                The return value of method `name` when executed.
            `callbacks`: list
                The list of callbacks associated with method `name`.

        :Returns:
            A bool indicating whether a callback has been added and the main
            thread needs to execute them.
        '''
        got_callback = False
        cls_method = event.cls_method
        for ev in callbacks[:]:
            if ((ev.trigger and ev is not event) or
                cls_method is not ev.cls_method or ev not in callbacks):
                continue

            if ev.callback is None:
                if not ev.repeat:
                    try:
                        callbacks.remove(ev)
                    except ValueError:
                        pass
                continue

            scheduled_callbacks = ev.scheduled_callbacks
            if len(scheduled_callbacks) and not ev.repeat:
                continue
            scheduled_callbacks.append((result, event))
            got_callback = True

        return got_callback

    def _service_main_thread(self, *largs, **kwargs):
        '''The method executed by the main thread when there are execution
        results and callbacks to be executed.
        '''
        callbacks = self.__callbacks

        for name in list(callbacks.keys()):
            cb = callbacks[name]
            for ev in cb[:]:
                if not len(ev.scheduled_callbacks):
                    continue

                scheduled_callbacks = ev.scheduled_callbacks[:]
                f = ev.callback

                for result, event in scheduled_callbacks:
                    if ev not in cb:
                        break
                    if ev.trigger:
                        f(result)
                    else:
                        f(result, kw_in=event.func_kwargs)

                if not ev.repeat:
                    try:
                        cb.remove(ev)
                    except ValueError:
                        pass
                del ev.scheduled_callbacks[:len(scheduled_callbacks)]

    def _callback_thread(self):
        '''The internal thread that executes the scheduled methods.
        '''
        callbacks = self.__callbacks
        lock = self.__callback_lock
        event = self.__thread_event
        schedule = self._schedule_thread_callbacks
        trigger = self._kivy_trigger
        handler = self.handle_exception

        try:
            while 1:
                event.wait()
                if self.__signal_exit:
                    break
                has_events = False
                with lock:
                    keys = list(callbacks.keys())
                    event.clear()

                for key in keys:
                    cb = callbacks[key]
                    for ev in cb[:]:
                        if self.__signal_exit:
                            self.__thread = None
                            return

                        # the order of these checks cannot be changed because
                        # it needs to be inverse order of _service_main_thread
                        if (not ev.trigger or (not ev.repeat and len(
                            ev.scheduled_callbacks)) or ev not in cb):
                            continue

                        f = getattr(
                            self if ev.cls_method else self.target, key)
                        try:
                            failed = None
                            res = f(**ev.func_kwargs)
                        except Exception as e:
                            failed = True
                            retry = handler((e, traceback.format_exc()), ev)
                            skip = False
                            while retry:
                                try:
                                    if ev not in cb:
                                        skip = True
                                        break
                                    res = f(**ev.func_kwargs)
                                    failed = retry = None
                                except Exception as e:
                                    failed = True
                                    retry = bool(handler((e, sys.exc_info()),
                                                         ev))
                            if skip:
                                continue
                        if failed:
                            self.__thread = None
                            return

                        if ev.repeat:
                            has_events = True
                        if schedule(key, ev, res, cb):
                            trigger()
                if has_events or self.__signal_exit:
                    event.set()
        except Exception as e:
            handler((e, traceback.format_exc()), None)
        self.__thread = None
