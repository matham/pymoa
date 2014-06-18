from __future__ import absolute_import

from threading import Event, RLock
from kivy.clock import ClockBase, _default_time
import time


class MoaClockBase(ClockBase):

    _sleep_event = None

    def __init__(self, **kwargs):
        self._sleep_event = Event()
        super(MoaClockBase, self).__init__(**kwargs)

    def create_trigger(self, callback, timeout=0, priority=False):
        '''Create a Trigger event. Check module documentation for more
        information.

        .. versionadded:: 1.0.5
        '''
        ev = super(MoaClockBase, self).create_trigger(callback, timeout)
        ev.priority = priority
        return ev

    def schedule_once(self, callback, timeout=0, priority=False):
        '''Schedule an event in <timeout> seconds. If <timeout> is unspecified
        or 0, the callback will be called after the next frame is rendered.

        .. versionchanged:: 1.0.5
            If the timeout is -1, the callback will be called before the next
            frame (at :meth:`tick_draw`).

        '''
        ev = super(MoaClockBase, self).schedule_once(callback, timeout)
        ev.priority = priority
        return ev

    def schedule_interval(self, callback, timeout, priority=False):
        '''Schedule an event to be called every <timeout> seconds.'''
        ev = super(MoaClockBase, self).schedule_interval(callback, timeout)
        ev.priority = priority
        return ev

    def tick(self):
        '''Advance the clock to the next step. Must be called every frame.
        The default clock has a tick() function called by the core Kivy
        framework.'''

        self._release_references()
        if self._fps_counter % 100 == 0:
            self._remove_empty()

        # do we need to sleep ?
        if self._max_fps > 0:
            min_sleep = self.MIN_SLEEP
            sleep_undershoot = self.SLEEP_UNDERSHOOT
            fps = self._max_fps
            usleep = self.usleep

            sleeptime = 1 / fps - (_default_time() - self._last_tick)
            while sleeptime - sleep_undershoot > min_sleep:
                self._sleep_event.clear()
                self._process_events(only_priority=True)
                #time.sleep(0)
                self._sleep_event.wait(sleeptime - sleep_undershoot)
                sleeptime = 1 / fps - (_default_time() - self._last_tick)

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
        self._process_events()

        return self._dt

    def _process_events(self, only_priority=False):
        events = self._events
        for cid in list(events.keys())[:]:
            for event in events[cid][:]:
                if only_priority:
                    try:
                        if not event.priority:
                            continue
                    except AttributeError:
                        continue
                    self._sleep_event.set()
                if event.tick(self._last_tick) is False:
                    # event may be already removed by the callback
                    if event in events[cid]:
                        events[cid].remove(event)
