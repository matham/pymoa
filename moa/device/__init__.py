'''Device module for interfacing Moa with devices (e.g switches, ADC, etc.).
'''

from kivy.properties import BooleanProperty
from moa.base import MoaBase


class Device(MoaBase):
    '''The base class for all devices interfacing with Moa.

    :Events:

        `on_data_update`:
            Should be fired after the devices data has been updated. See
            individual classes for details.

            Listening or binding to the state property for changes, e.g.
            :attr:`~moa.device.adc.ADCPort.data` for the ADC, will notify when
            the data has changed, but if e.g. the ADC reads identical data
            continuously, e.g. with a DC signal, then the callbacks will
            not be triggered and you won't be notified that the ADC has read
            new data. Listening to to `on_data_update` however, should always
            notify of new data, even the data is identical
    '''

    __events__ = ('on_data_update', )

    _activated_set = None
    '''A set of the `identifier` passed to :meth:`activate`. It keeps track
    of which ids have activated the device.
    '''

    def __init__(self, **kwargs):
        super(Device, self).__init__(**kwargs)
        self._activated_set = set()

    def activate(self, identifier, **kwargs):
        '''Called to activate the device.

        The method is overwritten and called by inherited widgets to check
        whether the device is already active or the activation code should
        be executed.

        :Parameters:

            `identifier`: hashable object
                The hash associated with this request. This is needed when
                :meth:`deactivate` is called. See :meth:`deactivate`. If this
                `identifier` has already been used it is ignored.

        :Returns:
            True if the device should be activated, False otherwise.
        '''
        active = self._activated_set
        result = len(active) == 0
        active.add(identifier)
        if result:
            self.is_active = True
            self.log('debug', 'Activating with {}', identifier)
        else:
            self.log('debug', 'Activating skipped with {}', identifier)
        return result

    def deactivate(self, identifier, clear=False, **kwargs):
        '''Called to deactivate the device.

        The method is overwritten and called by inherited widgets to check
        whether the device is active and the deactivation code should be
        executed.

        Typically multiple users may activate or deactivate a device
        independently. The device should become active only on the first
        request, and it should deactivate only after all requests have been
        deactivated. `identifier` is used to track these requests.

        The first time a :meth:`activate` request is made, the device is
        activated. Subsequently, we just store `identifier` and
        :meth:`activate` returns False. Following, all :meth:`decativate`
        requests return False, until there is only one `identifier` remaining,
        which upon its removal, it returns True and the device can be
        deactivated.

        :Parameters:

            `identifier`: hashable object
                The hash used to with :meth:`activate`. If the `identifier`
                doesn't exist, it is ignored.
            `clear`: bool
                Whether all `identifier` values passed with :meth:`activate`
                should be removed.

        :Returns:
            True if the device should be deactivated, False otherwise.

        For example::

            >>> from moa.device import Device
            >>> class MyDevice(Device):
                >>> def activate(self, identifier, **kwargs):
                ...     if super(MyDevice, self).activate(identifier, \
**kwargs):
                ...         print('Activating with {}'.format(identifier))
                ...         return True
                ...     print('Skipping activation with {}'.format(identifier))
                ...     return False
                ...
                ... def deactivate(self, identifier, **kwargs):
                ...     if super(MyDevice, self).deactivate(identifier, \
**kwargs):
                ...         print('De-activating with {}'.format(identifier))
                ...         return True
                ...     print('Skipping deactivation with {}'.\
format(identifier))
                ...     return False

            >>> dev = MyDevice()
            >>> dev.activate(55)
            Activating with 55
            >>> dev.activate(55)
            Skipping activation with 55
            >>> dev.activate(dev)
            Skipping activation with <__main__.MyDevice object at 0x027DA730>
            >>> dev.deactivate(55)
            Skipping deactivation with 55
            >>> dev.deactivate(dev)
            De-activating with <__main__.MyDevice object at 0x027DA730>
        '''
        active = self._activated_set
        old_len = len(active)

        if clear:
            active.clear()
        else:
            try:
                active.remove(identifier)
            except KeyError:
                pass

        result = bool(old_len and not len(active))
        if result:
            self.is_active = False
            self.log('debug', 'De-activating with {}', identifier)
        else:
            self.log('debug', 'De-activating skipped with {}', identifier)
        return result

    def on_data_update(self, instance):
        pass

    is_active = BooleanProperty(False)
    '''Whether the device is currently active. Defaults to False.
    See :meth:`activate`.
    '''
