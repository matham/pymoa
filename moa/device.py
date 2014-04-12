
from moa.threading import CallbackQueue
from moa.bases import MoaBase
from kivy.event import EventDispatcher
from kivy.properties import BooleanProperty
from kivy.clock import Clock
try:
    from Queue import Queue
except ImportError:
    from queue import Queue


class Device(MoaBase, EventDispatcher):
    ''' By default, the device does not support multi-threading.
    '''

    __events__ = ('on_restart', )

    active = BooleanProperty(False)

    _kivy_eventloop_queue = None

    def __init__(self, allow_async=True, **kwargs):
        super(Device, self).__init__(**kwargs)

        if allow_async:
            trigger = Clock.create_trigger(self._do_queue)
            self._kivy_eventloop_queue = CallbackQueue(trigger)

    def __del__(self):
        self.deinit()

    def _do_queue(self, *largs, **kwargs):
        while 1:
            try:
                key, val = self._kivy_eventloop_queue.get()
            except Queue.Empty:
                return
            if key == 'set':
                setattr(*val)
            elif key == 'call':
                f, l, kw = val
                f(*l, **kw)

    def init(self, **kwargs):
        pass

    def restart(self, **kwargs):
        pass

    def on_restart(self, **kwargs):
        pass

    def deinit(self, **kwargs):
        pass


class InputDevice(Device):

    __events__ = ('on_data', )

    def on_data(self, **kwargs):
        pass


class OutputDevice(Device):

    pass
