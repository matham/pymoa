"""Devices
============

Device module for interfacing Moa with devices (e.g switches, ADC, etc.).
"""

from pymoa.executor.remote import RemoteReferencable

__all__ = ('Device', )


class Device(RemoteReferencable):
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

    _logged_trigger_names_ = ('on_data_update', )

    def on_data_update(self, instance):
        pass

    def __repr__(self):
        cls = self.__class__
        cls_name = cls.__module__ + '.' + cls.__qualname__
        return f'<{cls_name} name="{self.name}">'
