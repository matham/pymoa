'''ADC implementation of :class:`~moa.device.Device`.
'''

__all__ = ('ADCPort', 'VirtualADCPort')

from kivy.properties import (
    DictProperty, BooleanProperty, NumericProperty, ObjectProperty,
    ListProperty)
from moa.device import Device
from time import clock
from kivy.clock import Clock


class ADCPort(Device):
    '''Abstract class that represents a multi-channel ADC.

    For ADCs whose channels are sampled independently, each should be given
    their own :class:`ADCPort` instance. It typically only makes sense to
    bundle multiple channels in one instance if they are sampled synchronously.
    '''

    timestamp = NumericProperty(0)
    '''The timestamp of the last update to the :attr:`raw_data`, and
    :attr:`data` attributes.

    Typically, the rule is that :attr:`timestamp` and :attr:`ts_idx` are
    updated before any of the `data` attributes ensuring that when
    responding to a data update, :attr:`timestamp` is accurate.
    The `on_data_update` event is fired after all the relevant channel data
    has been updated.

    :attr:`timestamp` is a :kivy:class:`~kivy.properties.NumericProperty` and
    defaults to 0.

    .. note::
        Typically, when activating, the :attr:`timestamp` is not updated.
    '''

    raw_data = ListProperty(None)
    '''A list of length :attr:`num_channels` containing the raw data for each
    channel. The structure is similar to :attr:`data`.

    As opposed to :attr:`data` which keeps the data as floats representing the
    actual signal being sensed, :attr:`raw_data` stores the data as a raw n-bit
    unsigned integer. Each value in :attr:`data` is derived from an identical
    element in :attr:`raw_data` using the following formula:

    :attr:`data` = :attr:`raw_data` * :attr:`scale` / (2 ^ :attr:`bit_depth`
    ) - :attr:`offset`.

    The reverse conversion: :attr:`raw_data` = (:attr:`data` + :attr:`offset`
    ) * (2 ^ :attr:`bit_depth`) / :attr:`scale`.

    :attr:`raw_data` is a :kivy:class:`~kivy.properties.ListProperty` and
    defaults to None.
    '''

    data = ListProperty(None)
    '''A list of length :attr:`num_channels` containing the properly rescaled
    floating point data for each channel.

    Each element in the list is a list type containing the most recent data
    read by the ADC. Rather than appending new data to old data, each new data
    slice read replaces the previously read data so that :attr:`data` only
    contains the most recently read data for each channel. Channels that are
    not read at a particular update will be represented by a empty list type.

    :attr:`data` is a :kivy:class:`~kivy.properties.ListProperty` and
    defaults to None.
    '''

    ts_idx = ListProperty(None)
    '''A list of length :attr:`num_channels`, where each element in the list
    indicates the index in :attr:`data` and :attr:`raw_data` that is
    timestamped by :attr:`timestamp`. The :attr:`timestamp` is the time of
    a data point for each channel. This data point can be different for each
    channel, so the index indicates the corresponding data point read at the
    time of :attr:`timestamp`.

    :attr:`ts_idx` is a :kivy:class:`~kivy.properties.ListProperty` and
    defaults to None.
    '''

    active_channels = ListProperty(None)
    '''A list of booleans with length :attr:`num_channels` indicating whether
    each corresponding channel is active. Inactive channels are ones that don't
    get data.

    :attr:`active_channels` is a :kivy:class:`~kivy.properties.ListProperty`
    and defaults to None.
    '''

    num_channels = NumericProperty(1)
    '''The number of channels in the ADC.

    :attr:`num_channels` is a :kivy:class:`~kivy.properties.NumericProperty`
    and defaults to 1.
    '''

    bit_depth = NumericProperty(0)
    '''The number of bits of :attr:`raw_data` data points. If zero, only
    :attr:`data` is populated.

    :attr:`bit_depth` is a :kivy:class:`~kivy.properties.NumericProperty`
    and defaults to 0.
    '''

    scale = NumericProperty(1.)
    '''The scale when converting :attr:`raw_data` to :attr:`data`.

    :attr:`scale` is a :kivy:class:`~kivy.properties.NumericProperty`
    and defaults to 1.0.
    '''

    offset = NumericProperty(0)
    '''The offset when converting :attr:`raw_data` to :attr:`data`.

    :attr:`offset` is a :kivy:class:`~kivy.properties.NumericProperty`
    and defaults to 0.0.
    '''

    frequency = NumericProperty(0)
    '''The frequency at which each ADC channel is sampled.

    :attr:`frequency` is a :kivy:class:`~kivy.properties.NumericProperty`
    and defaults to 0.0.
    '''


class VirtualADCPort(ADCPort):
    '''A virtual implementation of :class:`ADCPort`.

    The class simulates an ADC device with channel data generation. The
    :class:`ADCPort` conversion parameters must be initialized and once
    activated will start updating the channel data using the :attr:`data_func`
    callback.

    For example::

        >>> from moa.device.adc import VirtualADCPort
        >>> from math import cos, pi
        >>> class ADC(VirtualADCPort):
        ...     def __init__(self, **kwargs):
        ...         super(ADC, self).__init__(**kwargs)
        ...         self.scale = 10
        ...         self.offset = 5
        ...
        ...         def next_point(idx, channel):
        ...             rate = 1
        ...             if channel == 0:
        ...                 return .2 * cos(2 * pi * idx * rate / \
float(self.frequency))
        ...             return 4 * cos(2 * pi * idx * rate / float(\
self.frequency))
        ...         self.data_func = next_point
        ...
        ...     def on_data_update(self, *largs):
        ...         print('Data ({:.2f}): {}'.format(self.timestamp, \
self.data))
        ...         print('Raw data ({:.2f}): {}'.format(self.timestamp, \
self.raw_data))

        >>> adc = ADC(num_channels=2, active_channels=[True, True], \
data_size=2, frequency=4, bit_depth=16)
        >>> adc.activate(adc)
        Data (1.26): [[0.2, 0.0], [4.0, 0.0]]
        Raw data (1.26): [[34078, 32768], [58982, 32768]]
        Data (1.52): [[-0.2, 0.0], [-4.0, 0.0]]
        Raw data (1.52): [[31457, 32768], [6553, 32767]]
        Data (1.77): [[0.2, 0.0], [4.0, 0.0]]
        Raw data (1.77): [[34078, 32768], [58982, 32768]]
        ...
    '''

    data_func = ObjectProperty(None)
    '''A callback that is called when we need a new data point. The callback
    takes two parameters; a index parameter which is the index of the data
    point requested, and the channel number for which the data is requested.
    The function returns the generated sample value for that index and channel.

    .. note::
        The data returned is for :attr:`ADCPort.data`, :attr:`ADCPort.raw_data`
        values are computed from it.

    :attr:`data_func` is a :kivy:class:`~kivy.properties.ObjectProperty` and
    defaults to None.
    '''

    data_size = NumericProperty(0)
    '''The number of data points generated at once. That is for every update
    to the data parameters, :attr:`data_size` data points are generated. This
    simulates the buffer size of an ADC which passes to the caller data points
    in blocks of :attr:`data_size`.

    .. note::
        The data is generated in approximate real time according to
        :attr:`data_size` and :attr:`ADCPort.frequency`.

    :attr:`data_size` is a :kivy:class:`~kivy.properties.NumericProperty` and
    defaults to 0.
    '''

    _count = 0  # the last index passed to data_func, set for each block

    _start_time = 0  # the time when device was activated.

    def _generate_data(self, *l):
        t = clock()
        i = self._count
        count = self.data_size
        # ensure it's time to update
        if int((t - self._start_time) * self.frequency) - i < count:
            return

        f = self.data_func
        n = self.num_channels
        chs = self.active_channels
        offset = self.offset
        scale = self.scale
        depth = 2 ** self.bit_depth

        data = [[f(j + i, k) for j in range(count)] if chs[k] else []
                for k in range(n)]
        self._count = i + count
        self.timestamp = t
        self.ts_idx = [0, ] * n
        if depth == 1:
            if not self.raw_data:
                self.raw_data = [[] for d in data]
        else:
            self.raw_data = [[int((val + offset) / scale * depth) for val in d]
                             for d in data]
        self.data = data
        self.dispatch('on_data_update', self)

    def activate(self, *largs, **kwargs):
        if not super(VirtualADCPort, self).activate(*largs, **kwargs):
            return False
        self._count = 0
        self._start_time = clock()
        f = self.data_size / float(self.frequency)
        Clock.schedule_interval(self._generate_data, f / 2.)
        self.activation = 'active'
        return True

    def deactivate(self, *largs, **kwargs):
        if not super(VirtualADCPort, self).deactivate(*largs, **kwargs):
            return False
        Clock.unschedule(self._generate_data)
        self.activation = 'inactive'
        return True
