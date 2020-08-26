"""Device
=========

Device module for interfacing Moa with devices (e.g switches, ADC, etc.).
"""
from kivy.event import EventDispatcher

from pymoa.base import MoaBase

__all__ = ('Device', )


class Device(MoaBase, EventDispatcher):
    """The base class for all devices interfacing with Moa.

    :Events:

        `on_data_update`:
            Should be fired after the devices data has been updated. See
            individual classes for details.

            Listening or binding to the state property for changes, e.g.
            :attr:`~pymoa.device.adc.ADCPort.data` for the ADC, will notify
            when the data has changed, but if e.g. the ADC reads identical data
            continuously, e.g. with a DC signal, then the callbacks will
            not be triggered and you won't be notified that the ADC has read
            new data. Listening to to `on_data_update` however, should always
            notify of new data, even the data is identical
    """

    __events__ = ('on_data_update', )

    _logged_names_hint_ = ('on_data_update', )

    timestamp: float = 0
    '''The time stamp of the last update to the device.

    .. warning::
        The :attr:`timestamp` may be derived from a device clock different than
        the local clock. One needs to be aware of the timestamp source.
    '''

    def on_data_update(self, instance):
        pass
