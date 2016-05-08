'''Clock module similar to :kivy:class:`~kivy.clock`. It provides a `Clock`
object used to schedule callbacks with the kivy Clock.

In addition to the normal kivy Clock methods, one can also schedule priority
events which should be executed immediately and is not frame rate limited.

In order to use this clock, one must call :func:`set_clock` before doing
anything kivy related (except e.g. importing kivy and other modules that
don't schedule any kivy callbacks). This is accomplished by setting the
environmental variable of `MOA_CLOCK` to `'1'` and then importing moa.

For example using this definition::

    from os import environ
    environ['MOA_CLOCK'] = '1'
    import moa

    from kivy.app import runTouchApp
    from kivy.uix.widget import Widget
    from kivy.clock import Clock
    from time import clock

    class Events(Widget):

        trigger = None
        t = clock()

        def __init__(self, priority=False, **kwargs):
            super(Events, self).__init__(**kwargs)
            if priority:
                self.trigger = Clock.create_trigger_priority(self.callback, \
timeout=0.001)
            else:
                self.trigger = Clock.create_trigger(self.callback, timeout=0.001)
            self.trigger()

        def callback(self, *l):
            t = clock()
            print 'fps', 1 / (t - self.t)
            self.t = t
            self.trigger()

Running `runTouchApp(Events())` prints::

    ...
    fps 76.9822032559
    fps 77.0284665992
    fps 50.6727424053
    fps 76.7734938999
    fps 62.4892743508
    fps 71.3713146943
    ...

Running `runTouchApp(Events(priority=True))` prints::

    ...
    fps 780.305030439
    fps 831.739071038
    fps 900.640532544
    fps 891.083790706
    fps 887.511661808
    fps 903.31305638
    ...

'''
from __future__ import absolute_import

__all__ = ('PriorityClockEvent', )

from threading import Event
from os import environ
import kivy
from kivy.clock import ClockBase, ClockEvent, _default_time, _hash
from kivy.clock import Clock as KivyClock
from kivy.context import register_context
from functools import partial


class PriorityClockEvent(ClockEvent):
    '''Similar to :kivy:class:`~kivy.clock.ClockEvent`, except the event
    might have priority and then its execution is not frame rate limited.
    '''

    priority = False
    '''Whether this event's execution is frame rate limited.
    '''

    def __init__(self, priority, clock, loop, callback, timeout, starttime,
                 cid, trigger=False):
        super(PriorityClockEvent, self).__init__(clock, loop, callback,
            timeout, starttime, cid, trigger)
        self.priority = priority
        if trigger and priority:
            self.clock._sleep_event.set()

    def __call__(self, *largs):
        if self._is_triggered is False:
            self._is_triggered = True
            priority = self.priority
            # update starttime
            self._last_dt = (_default_time() if priority else
                             self.clock._last_tick)
            self.clock._events[self.cid].append(self)
            if self.priority:
                self.clock._sleep_event.set()
            return True

    def tick(self, curtime, remove):
        if self.priority and curtime - self._last_dt < self.timeout:
            return True
        return super(PriorityClockEvent, self).tick(curtime, remove)


class MoaClockBase(ClockBase):
    '''Similar to :kivy:class:`~kivy.clock.ClockBase`, except the clock allows
    events which may have priority and then their execution is not frame rate
    limited.

    To schedule a priority event call the `xxx_priority` methods.
    '''

    _sleep_event = None
    MIN_SLEEP = 0.005
    SLEEP_UNDERSHOOT = MIN_SLEEP - 0.001

    def __init__(self, **kwargs):
        self._sleep_event = Event()
        super(MoaClockBase, self).__init__(**kwargs)

    def tick(self):
        '''Advance the clock to the next step. Must be called every frame.
        The default clock has a tick() function called by the core Kivy
        framework.'''

        self._release_references()
        process_events = self._process_events

        # do we need to sleep ?
        if self._max_fps > 0:
            min_sleep = self.MIN_SLEEP
            sleep_undershoot = self.SLEEP_UNDERSHOOT
            fps = self._max_fps
            _events = self._events
            last_tick = self._last_tick
            sleep_event = self._sleep_event

            def rem_sleep():
                # any event added after this will set the flag
                sleep_event.clear()
                t = _default_time()
                sleeptime = val = 1 / fps - (t - last_tick)
                for events in _events:
                    for event in events[:]:
                        if event.priority:
                            val = min(val,
                                      event.timeout - (t - event._last_dt))
                return max(val, 0), sleeptime

            eventtime, sleeptime = rem_sleep()
            while sleeptime - sleep_undershoot > min_sleep:
                sleep_event.wait(max(eventtime - sleep_undershoot, 0))
                process_events(_default_time, priority=True)
                eventtime, sleeptime = rem_sleep()

        # tick the current time
        current = _default_time()
        self._dt = current - self._last_tick
        self._frames += 1
        self._fps_counter += 1
        self._last_tick = current

        # calculate fps things
        if self._last_fps_tick is None:
            self._last_fps_tick = current
        elif current - self._last_fps_tick > 1:
            d = float(current - self._last_fps_tick)
            self._fps = self._fps_counter / d
            self._rfps = self._rfps_counter
            self._last_fps_tick = current
            self._fps_counter = 0
            self._rfps_counter = 0

        # process event
        process_events(_default_time, current)

        return self._dt

    def create_trigger(self, callback, timeout=0):
        ev = PriorityClockEvent(False, self, False, callback, timeout, 0,
                                _hash(callback))
        ev.release()
        return ev

    def schedule_once(self, callback, timeout=0):
        if not callable(callback):
            raise ValueError('callback must be a callable, got %s' % callback)
        event = PriorityClockEvent(False, self, False, callback, timeout,
            self._last_tick,
            _hash(callback), True)
        return event

    def schedule_interval(self, callback, timeout):
        if not callable(callback):
            raise ValueError('callback must be a callable, got %s' % callback)
        event = PriorityClockEvent(False, self, True, callback, timeout,
            self._last_tick,
            _hash(callback), True)
        return event

    def create_trigger_priority(self, callback, timeout=0):
        '''Similar to :kivy:meth:`~kivy.clock.ClockBase.create_trigger`,
        except the created event has priority.
        '''
        ev = PriorityClockEvent(True, self, False, callback, timeout, 0,
                                _hash(callback))
        ev.release()
        return ev

    def schedule_once_priority(self, callback, timeout=0):
        '''Similar to :kivy:meth:`~kivy.clock.ClockBase.schedule_once`,
        except the created event has priority.
        '''
        if not callable(callback):
            raise ValueError('callback must be a callable, got %s' % callback)
        event = PriorityClockEvent(True, self, False, callback, timeout,
            _default_time(),
            _hash(callback), True)
        return event

    def schedule_interval_priority(self, callback, timeout):
        '''Similar to :kivy:meth:`~kivy.clock.ClockBase.schedule_interval`,
        except the created event has priority.
        '''
        if not callable(callback):
            raise ValueError('callback must be a callable, got %s' % callback)
        event = PriorityClockEvent(True, self, True, callback, timeout,
            _default_time(),
            _hash(callback), True)
        return event

    def _process_events(self, clock, last_tick=None, priority=False):
        for events in self._events:
            remove = events.remove
            for event in events[:]:
                # event may be already removed from original list
                if event in events:
                    if event.priority:
                        event.tick(clock(), remove)
                    elif not priority:
                        event.tick(last_tick, remove)


def set_clock(clock='kivy'):
    '''Sets whether the main kivy Clock (:kivy:attr:`~kivy.clock.Clock`) and
    :attr:`~moa.clock.Clock` will use the default Kivy clock or the moa clock
    with available priority (:class:`~moa.clock.MoaClockBase`). If the default
    kivy clock is used, the `xxx_priority` methods map to the normal methods.

    This method must be called before any kivy modules that may schedule
    callbacks or use the clock are imported/called. Setting it through the
    environment variable `MOA_CLOCK` is currently the only way to ensure the
    moa clock will work correctly.

    By default, once the :mod:`~moa.clock` is imported, the kivy
    :kivy:attr:`~kivy.clock.Clock` gets priority methods, which are mapped
    to the normal methods.

    See module for examples.
    '''
    if clock not in ('kivy', 'moa'):
        raise Exception('Clock "{}" not recognized'.format(clock))

    Clock = ClockBase if clock == 'kivy' else MoaClockBase
    kivy.clock.Clock = globals()['Clock'] = Clock = \
        register_context('Clock', Clock)

    if clock == 'kivy':
        Clock.create_trigger_priority = Clock.create_trigger
        Clock.schedule_once_priority = Clock.schedule_once
        Clock.schedule_interval_priority = Clock.schedule_interval


Clock = KivyClock
if 'KIVY_DOC_INCLUDE' not in environ:
    Clock.create_trigger_priority = Clock.create_trigger
    Clock.schedule_once_priority = Clock.schedule_once
    Clock.schedule_interval_priority = Clock.schedule_interval
