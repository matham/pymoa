'''Threading
=============
'''

from __future__ import absolute_import

from collections import defaultdict
from threading import RLock, Event, Thread
import sys

from kivy.clock import Clock

__all__ = ('ScheduledEvent', 'ScheduledEventLoop')


class ScheduledEvent(object):
    '''An internal class used and returned when scheduling an event with
    :meth:`ScheduledEventLoop.request_callback`.
    '''

    repeat = False
    '''Whether the event is a one time shot, or repeats until removed.
    Applies whether :attr:`trigger` is True or False.
    '''

    kw_in = 'kw_in'
    '''When calling the :attr:`callback`, if :attr:`trigger` was False
    :attr:`func_kwargs` is passed back to the :attr:`callback` using the
    keyword name :attr:`kw_in`.
    '''

    func_kwargs = {}
    '''The keyword args passed to the :attr:`name` function when it's executed.
    '''

    callback = None
    '''After the scheduled method :attr:`name` has been executed,
    :attr:`callback` is the callback function to be executed from the kivy
    event loop with the execution result.
    '''

    scheduled_callbacks = []
    '''List of callbacks for this event scheduled to be executed by the kivy
    thread. These notify the original scheduler that the event completed.

    The elements in the list are 2-tuples of the result of the execution of
    :attr:`name`, followed by the :class:`ScheduledEvent` that caused the
    execution.
    '''

    trigger = True
    '''Whether this event is a trigger event.

    With `trigger` True the event is
    a normal event. If :attr:`trigger` is False, then the event will not
    execute on its own, but will listen to other events associated with
    the same method. That is, it will get callbacks for every execution of
    the method :attr:`name` and :attr:`obj` that match this one.

    Also, if `trigger` is False, :attr:`callback` will get a keyword argument
    called :attr:`kw_in`, which is the :attr:`func_kwargs`.
    '''

    obj = None
    '''The object with the method :attr:`name` which will be called from the
    event loop thread. None means :attr:`name` is a not a method but a
    function.
    '''

    name = ''
    '''The name of the method associated with this event. See
    :meth:`ScheduledEventLoop.request_callback`. If :attr:`obj` is None then
    this is an actual function, otherwise :attr:`name` is a method of object
    :attr:`obj`.
    '''

    def __init__(self, callback=None, func_kwargs={}, repeat=False,
                 trigger=False, obj=None, name='', kw_in='kw_in'):
        self.callback = callback
        self.func_kwargs = func_kwargs
        self.repeat = repeat
        self.scheduled_callbacks = []
        self.trigger = trigger
        self.name = name
        self.obj = obj
        self.kw_in = kw_in


class ScheduledEventLoop(object):
    '''This class provides a scheduling mechanism though which functions are
    executed from an internal thread specific to this instance. This eases
    execution of methods outside the main system thread. After execution, if
    set, the main (Kivy) thread executes a callback using the execution result.

    The class also deals with exceptions transparently using
    :meth:`handle_exception`.

    :Parameters:

        `daemon`: bool
            Whether the internal thread is a daemon thread. Defaults to False.

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
                print('got exception "{}" for event with name "{}" and kwargs'
                    ' "{}"'.format(e, event.name, event.func_kwargs))
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

    def __init__(self, daemon=False, **kwargs):
        super(ScheduledEventLoop, self).__init__(**kwargs)
        self._daemon = daemon
        self.__callback_lock = RLock()
        self.__thread_event = Event()
        self.__callbacks = defaultdict(list)
        self._kivy_trigger = Clock.create_trigger_free(
            self._service_main_thread)
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

        :meth:`start_thread` is automatically called when the instance is
        created.
        '''
        if self.__thread is not None:
            return
        self.__signal_exit = False
        self.__thread_event.set()
        self.__thread = Thread(
            target=self._callback_thread,
            name='ScheduledEventLoop ({})'.format(self))
        self.__thread.daemon = self._daemon
        self.__thread.start()

    def stop_thread(self, join=False, timeout=None, clear=True):
        '''Stops the internal thread. It does not modify any callbacks.

        This method is not multi-threading safe with :meth:`start_thread`, so
        it should only be called from the main kivy thread.

        :Parameters:

            `join`: bool
                If True, the calling thread will join the thread until it
                exits. Defaults to False.
            `timeout`: float, int
                When ``join`` is True, ``timeout`` is how long to wait on the
                thread to die before continuing. Defaults to None (i.e. never
                time out).
            `clear`: bool
                If True, :meth:`clear` is called automatically. Defaults
                to True.

        :returns:

            True if the thread is dead, False if otherwise (e.g. if it timed
            out).
        '''
        self.__signal_exit = True
        self.__thread_event.set()
        thread = self.__thread
        if join and thread is not None:
            thread.join(timeout=timeout)

        if clear:
            self.clear_events()

        if thread is not None:
            return not thread.is_alive()
        return True

    def handle_exception(self, exception, event):
        ''' Called from the internal thread when the function executed within
        the thread raises an exception. It should be overwritten by the derived
        class.

        :Parameters:

            `exception`: 2-tuple
                tuple of the Exception (``e``) and ``sys.exc_info()``.
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
                         repeat=False, obj=None, kw_in='kw_in', **kwargs):
        '''Adds a function to be executed by the internal thread.
        See :class:`ScheduledEvent`.

        :Parameters:

            `name`: str
                If ``obj`` is None, it's the function, otherwise it's the name
                of ``obj`` 's method which will be executed from the internal
                thread. See :attr:`ScheduledEvent.name`.
            `callback`: object
                A callback function which will be called by the main (kivy)
                thread with the results of the method `name` as executed by
                the internal thread.

                If `trigger` is False, the method will get a keyword argument
                named as the value of ``kw_in``, which is ``kwargs``. See
                :attr:`ScheduledEvent.func_kwargs`

                If None, no callback will be called. Defaults to None.
            `trigger`: bool
                See :attr:`ScheduledEvent.trigger`. Defaults to True.
            `repeat`: bool
                See :attr:`ScheduledEvent.repeat`. Defaults to False.
            `obj`: object or None
                See :attr:`ScheduledEvent.obj`. Defaults to None.
            `kw_in`: str
                See :attr:`ScheduledEvent.kw_in`. Defaults to ``'kw_in'``.
            `**kwargs`:
                The caught keyword arguments that will be passed to the
                function ``name``. See :attr:`ScheduledEvent.func_kwargs`.

        :Returns:
            A instance of :class:`ScheduledEvent`.

        .. note::
            The order with which :meth:`request_callback` is called is not
            necessarily the order in which the internal thread will execute
            them.
        '''
        ev = ScheduledEvent(
            callback=callback, func_kwargs=kwargs, repeat=repeat,
            trigger=trigger, obj=obj, name=name, kw_in=kw_in)
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

            `name`: str or callable.
                The name of the method. This should be the same as the ``name``
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
        obj = event.obj
        for ev in callbacks[:]:
            if ((ev.trigger and ev is not event) or
                    obj is not ev.obj or ev not in callbacks):
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
                        f(result, **{event.kw_in: event.func_kwargs})

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
                        if (not ev.trigger or
                            (not ev.repeat and len(ev.scheduled_callbacks)) or
                                ev not in cb):
                            continue

                        f = ev.name if ev.obj is None else \
                            getattr(ev.obj, ev.name)
                        try:
                            failed = None
                            res = f(**ev.func_kwargs)
                        except Exception as e:
                            failed = True
                            retry = handler((e, sys.exc_info()), ev)
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
            handler((e, sys.exc_info()), None)
        self.__thread = None
