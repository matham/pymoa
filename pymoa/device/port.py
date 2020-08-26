"""Channel Devices
====================

Some simple implementations of :class:`~pymoa.device.Device`. See classes
"""

from typing import List
from kivy.properties import ObjectProperty
from pymoa.device import Device

__all__ = ('ChannelBase', 'Channel', 'Port', )


class ChannelBase(Device):
    """A somewhat more concrete than
    :class:`~pymoa.device.Device` base class for general input/output devices.

    Following is the typical expected structure of these devices. Each channel
    represents some kind of interaction with the world. E.g. it might represent
    digital input lines and output switches, multi-channel ADCs, or analog
    output channels. It might event represent the graphical state of buttons.

    For each of these channels in the device, the instance should contain a
    property representing the channel state. For example, a single digital
    channel, :class:`~pymoa.device.digital.DigitalChannel`, contains a state
    variable indicating the state of the switch.

    From the outside, the property should be treated as read only. That is, if
    the channel controls a switch, one does not change
    :attr:`~pymoa.device.digital.DigitalChannel.state` to cause a change in the
    state, rather one calls :meth:`set_state`. Once :meth:`set_state` changes
    the state, it is its responsibility to update the `state` variable and
    e.g. :attr:`timestamp` and then emit a `on_data_update` event.

    Consequently, the pattern is for the device to update the state variables
    with every change to the device. From the outside, one calls
    :meth:`set_state` to change the state and then reads (or listens to) the
    property or `on_data_update` to get the current state, including after a
    call to :meth:`set_state`.

    See :mod:`~pymoa.device.analog` and :mod:`~pymoa.device.digital` for example
    devices.
    """

    async def write_state(self, **kwargs):
        """A abstract method for setting the state. See :class:`ChannelBase`
        for details.

        .. note::
            If supported, the method needs to be overwritten by a base class
            otherwise, it raises a `NotImplementedError`.
        """
        raise NotImplementedError

    async def read_state(self):
        """A abstract method causing a read of the state. This method should
        not return the state, but rather cause the device to read the state
        and update the appropriate instance property with the current state.

        .. note::
            If supported, the method needs to be overwritten by a base class
            otherwise, it raises a `NotImplementedError`.
        """
        raise NotImplementedError

    async def pump_state(self, *args, **kwargs):
        raise NotImplementedError


class Channel(ChannelBase):
    """Represents a device containing a single channel. E.g. a single analog
    i/o switch, a button, etc.

    For example a simple switch which does nothing::

        >>> from kivy.properties import BooleanProperty
        >>> class SimpleSwitch(Channel):
        ...     state = BooleanProperty(False, allownone=True)
        ...     async def set_state(self, state):
        ...         self.state = state

        >>> switch = SimpleSwitch()
        >>> switch.state
        False
        >>> switch.activate(switch)
        True
        >>> print(switch.state)
        None
        >>> switch.set_state(True)
        >>> switch.state
        True
    """
    pass


class Port(ChannelBase):
    """Device similar to :class:`Channel`, except this device represents
    one or more channels. E.g. a port with multiple digital lines, or a
    port of multiple buttons.

    Similar to :attr:`Channel.state`, the expectation is that each channel or
    line will have a property associated with it. The name of the property
    is any valid name representing whatever is connected. For example, if there
    are 2 digital lines connected to a light and IR beam break, the two
    properties might be named `light`, and `ir_beam`. This allows checking
    their state simply with e.g. `x.light`.

    Although a port is commonly represented by e.g. a list of the state of each
    channel, in this implementation each channel gets an individual property.

    .. warning::
        If :attr:`ChannelBase.reset_state` is True, then each of the channel
        properties must have `allownone=True`.

    For example::

        from kivy.properties import BooleanProperty
        >>> class DigitalPort(Port):
        ...     photobeam = BooleanProperty(False, allownone=True)
        ...     light = BooleanProperty(False, allownone=True)
        ...
        ...     def set_state(self, name, value):
        ...         print('Setting line {} to {}'.format(self.attr_map[name],\
 value))
        ...         setattr(self, name, value)
        ...
        >>> # photobeam controls physical line 2 and the light line 5
        >>> port = DigitalPort(attr_map={'photobeam': 2, 'light': 5})
        >>> print(port.photobeam)
        False
        >>> port.chan_attr_map
        {2: 'photobeam', 5: 'light'}
        >>> port.activate(port)
        True
        >>> # already active so it won't be activated again
        >>> port.activate(port)
        False
        >>> # reset_state is True, so the property is set None when activated
        >>> print(port.photobeam)
        None
        >>> port.set_state('photobeam', False)
        Setting line 2 to False
        >>> print(port.photobeam)
        False
        >>> port.deactivate(port)
        True
    """

    channel_names: List[str] = []
    '''List of name of the channels of the port.
    '''
