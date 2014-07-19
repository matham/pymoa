from __future__ import absolute_import

from threading import Event
from kivy.clock import ClockBase, ClockEvent, _default_time, _hash


class PriorityClockEvent(ClockEvent):

    priority = False

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

    def create_trigger(self, callback, timeout=0, priority=False):
        ev = PriorityClockEvent(priority, self, False, callback, timeout, 0,
                                _hash(callback))
        ev.release()
        return ev

    def schedule_once(self, callback, timeout=0, priority=False):
        if not callable(callback):
            raise ValueError('callback must be a callable, got %s' % callback)
        event = PriorityClockEvent(priority, self, False, callback, timeout,
            _default_time() if priority else self._last_tick,
            _hash(callback), True)
        return event

    def schedule_interval(self, callback, timeout, priority=False):
        if not callable(callback):
            raise ValueError('callback must be a callable, got %s' % callback)
        event = PriorityClockEvent(priority, self, True, callback, timeout,
            _default_time() if priority else self._last_tick,
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
