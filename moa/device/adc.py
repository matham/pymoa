

__all__ = ('ADCPort', 'VirtualADCPort')

from kivy.properties import (
    DictProperty, BooleanProperty, NumericProperty, ObjectProperty,
    ListProperty)
from moa.device import Device
from time import clock
from kivy.clock import Clock


class ADCPort(Device):

    #     def __init__(self, **kwargs):
    #         super(ADCPort, self).__init__(**kwargs)
    #         self.on_num_channels()
    #
    #     def on_num_channels(self, *largs):
    #         n = self.num_channels
    #         self.raw_data = [[] for _ in range(n)]
    #         self.data = [[] for _ in range(n)]
    #         self.ts_idx = [0, ] * n
    #         self.ts_idx = [0, ] * n

    timestamp = NumericProperty(0)
    ''' The time when things last updated. This is set just before the
    data is updated.
    '''

    raw_data = ListProperty(None)
    '''Data as raw of 2**n bit depth. Each element in list holds array-type
    data for that channel.
    '''

    data = ListProperty(None)
    '''Data as scaled doubles.
    '''

    ts_idx = ListProperty(None)

    active_channels = ListProperty(None)

    num_channels = NumericProperty(1)

    bit_depth = NumericProperty(0)
    '''If zero, only :attr:`data` is populated.
    '''

    scale = NumericProperty(1.)

    offset = NumericProperty(0)

    frequency = NumericProperty(0)


class VirtualADCPort(ADCPort):

    data_func = None

    data_size = NumericProperty(0)

    _count = 0

    _start_time = 0

    def _generate_data(self, *l):
        t = clock()
        i = self._count
        count = self.data_size
        if int((t - self._start_time) * self.frequency) - i < count:
            return

        f = self.data_func
        n = self.num_channels
        chs = self.active_channels
        offset = self.offset
        scale = self.scale
        depth = 2 ** self.bit_depth

        data = [[f(j + i) for j in range(count)] if chs[k] else []
                for k in range(n)]
        raw_data = [[(val + offset) / scale * depth for val in d]
                    for d in data]
        self._count = i + count
        self.timestamp = t
        self.ts_idx = [0, ] * n
        self.raw_data = raw_data
        self.data = data

    def activate(self, *largs, **kwargs):
        if not super(VirtualADCPort, self).activate(*largs, **kwargs):
            return False
        self._count = 0
        self._start_time = clock()
        f = self.data_size / float(self.frequency)
        Clock.schedule_interval(self._generate_data, f / 2.)
        return True

    def deactivate(self, *largs, **kwargs):
        if not super(VirtualADCPort, self).deactivate(*largs, **kwargs):
            return False
        Clock.unschedule(self._generate_data)
        return True
