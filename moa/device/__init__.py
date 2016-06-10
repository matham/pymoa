'''Devices
============

Device module for interfacing Moa with devices (e.g switches, ADC, etc.).
'''

from kivy.properties import OptionProperty
from moa.base import MoaBase

__all__ = ('Device', )


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

    def activate(self, identifier, state='active', **kwargs):
        '''Called to activate the device (:attr:`activation`).

        All devices have a concept of being active/inactive. When they are
        active they update their properties according to the data etc. When
        inactive, any hardware devices etc. are not being watched. To
        start, the device must be activated. See also :meth:`deactivate`.

        The method is overwritten and called by inherited devices to check
        whether the device is already active or if the activation code should
        be executed. So if this method returns False, it's already active/being
        activated or it cannot be activated. And the inherited class should
        not execute its activation code in that case.

        :Parameters:

            `identifier`: hashable object
                The hash associated with this request. This is needed when
                :meth:`deactivate` is called. See :meth:`deactivate`. If this
                `identifier` has already been used it is ignored and we return
                False.
            `state`: str
                Either `activating` or `active`. If `active`, the default, the
                device will immediately be set to active. Otherwise,
                the device must later be, when it becomes fully ready and
                active, activated by manually setting :attr:`activation` to
                `active`.

                Typical usage is for the inherited class to change `state` to
                `activating` rather than `active` when it cannot instatly
                activate the device. But it must remember to set it to active
                when done.

        :Returns:
            True if the device was currently activated, False otherwise.
        '''
        active = self._activated_set
        result = len(active) == 0
        active.add(identifier)
        activation = self.activation
        if result:
            if (activation != 'inactive' and activation != 'deactivating'):
                self.log('warning', 'Activated but activation was {}',
                         activation)
            self.activation = state
            self.log('debug', 'Activating with {}. Device was previously {}',
                     identifier, activation)
        else:
            if activation == 'active' or activation == 'activating':
                level = 'debug'
            else:
                level = 'warning'
            self.log(level, 'Activating skipped with {}. Device was '
                     'previously {}', identifier, activation)
        return result

    def deactivate(self, identifier, clear=False, state='inactive', **kwargs):
        '''Called to deactivate the device (:attr:`activation`).

        The method is overwritten and called by inherited devices to check
        whether the device is already inactive or if the deactivation code
        should be executed. So if this method returns False, it's already
        inactive/being deactivated or it cannot be deactivated. And the
        inherited class should not execute its deactivation code in that case.

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
                should be removed. Defaults to False.
            `state`: str
                Either `deactivating` or `inactive`. If `inactive`, the
                default, the device will immediately be set to inactive.
                Otherwise, the device must later be, when it becomes fully
                inactive, deactivated by manually setting :attr:`activation` to
                `inactive`.

        :Returns:
            True if the device should be deactivated, False otherwise.

        For example::

            >>> from moa.device import Device
            >>> class MyDevice(Device):
            >>>     def activate(self, identifier, **kwargs):
            ...         if super(MyDevice, self).activate(identifier,
            ...                                           **kwargs):
            ...             print('Activated with {}'.format(identifier))
            ...             return True
            ...         print('Skipping activation with {}'.format(identifier))
            ...         return False
            ...
            ...     def deactivate(self, identifier, **kwargs):
            ...         if super(MyDevice, self).deactivate(identifier,
            ...                                             **kwargs):
            ...             print('Deactivating with {}'.format(identifier))
            ...             return True
            ...         print(
            ...             'Skipping deactivation with {}'.format(identifier))
            ...         return False
            ...
            >>> dev = MyDevice()
            >>> dev.activate(55)
            Activated with 55
            >>> dev.activate(55)
            Skipping activation with 55
            >>> dev.activate(dev)
            Skipping activation with <__main__.MyDevice object at 0x027DA730>
            >>> dev.deactivate(55)
            Skipping deactivation with 55
            >>> dev.deactivate(dev)
            Deactivating with <__main__.MyDevice object at 0x027DA730>
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
        activation = self.activation
        if result:
            if (activation != 'active' and activation != 'activating'):
                self.log('warning', 'Deactivated but activation was {}',
                         activation)
            self.activation = state
            self.log('debug', 'Deactivating with {}. Device was previously {}',
                     identifier, activation)
        else:
            if ((activation == 'inactive' or activation == 'deactivating') and
                len(active) or
                (activation == 'active' or activation == 'activating') and
                    not old_len):
                level = 'warning'
            else:
                level = 'debug'
            self.log(level, 'Deactivating skipped with {}. Even though device '
                     'was previously {}', identifier, activation)
        return result

    def on_data_update(self, instance):
        pass

    activation = OptionProperty('inactive', options=[
        'active', 'inactive', 'activating', 'deactivating'])
    '''The activation state of the device.

    See :meth:`activate` and :meth:`deactivate`.

    :attr:`activation` is a :class:`~kivy.properties.OptionProperty`
    and defaults to `'inactive'`. Allowed values are `'active'`, `'inactive'`,
    `'activating'`, `'deactivating'`.
    '''
