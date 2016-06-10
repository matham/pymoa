'''Channel Devices
====================

Some simple implementations of :class:`~moa.device.Device`. See classes
'''

from kivy.properties import (
        DictProperty, OptionProperty, NumericProperty, ObjectProperty,
        BooleanProperty)
from moa.device import Device

__all__ = ('ChannelBase', 'Channel', 'Port', )


class ChannelBase(Device):
    '''A somewhat more concrete than :class:`~moa.device.Device` base class for
    general input/output devices.

    Following is the typical expected structure of these devices. Each channel
    represents some kind of interaction with the world. E.g. it might represent
    digital input lines and output switches, multi-channel ADCs, or analog
    output channels. It might event represent the graphical state of buttons.

    For each of these channels in the device, the instance should contain a
    property representing the channel state. For example, a single digital
    channel, :class:`~moa.device.digital.DigitalChannel`, contains a state
    variable indicating the state of the switch.

    From the outside, the property should be treated as read only. That is, if
    the channel controls a switch, one does not change
    :attr:`~moa.device.digital.DigitalChannel.state` to cause a change in the
    state, rather one calls :meth:`set_state`. Once :meth:`set_state` changes
    the state, it is its responsibility to update the `state` variable and
    e.g. :attr:`timestamp` and then emit a `on_data_update` event.

    Consequently, the pattern is for the device to update the state variables
    with every change to the device. From the outside, one calls
    :meth:`set_state` to change the state and then reads (or listens to) the
    property or `on_data_update` to get the current state, including after a
    call to :meth:`set_state`.

    See :mod:`~moa.device.analog` and :mod:`~moa.device.digital` for example
    devices.
    '''

    direction = OptionProperty('io', options=['i', 'o', 'io', 'oi'])
    '''The direction of the port channels of this device. A device can have
    either input or output channels, or both.

    :attr:`direction` is a :class:`~kivy.properties.OptionProperty` and
    defaults to `'io'`. It accepts `'i'`, `'o'`, `'io'`, or `'oi'`.
    '''

    timestamp = NumericProperty(0)
    '''The time stamp of the last update to the channel.

    Typically, the rule is that :attr:`timestamp` is updated before any of the
    attributes which are timed by :attr:`timestamp` is updated. It ensures
    that when responding to a attribute change, :attr:`timestamp` is accurate.
    The `on_data_update` event is fired after the complete data update.

    :attr:`timestamp` is a :class:`~kivy.properties.NumericProperty` and
    defaults to 0.

    .. note::
        Typically, when activating, the :attr:`timestamp` is not updated.

    .. warning::
        The :attr:`timestamp` may be derived from a device clock different than
        e.g. the Moa clock. One needs to be aware of the timestamp source.
    '''

    reset_state = BooleanProperty(True)
    '''Whether the state should be reset to `None` when it is activated.

    Whenever :meth:`activate` is called, if the base class returns True and
    :attr:`reset_state` is True, the state variable (or whatever its name) will
    be set to None. It's to indicate that the state is unknown until the first
    time it's updated.

    :attr:`reset_state` is a :class:`~kivy.properties.BooleanProperty` and
    defaults to True.
    '''

    def set_state(self, **kwargs):
        '''A abstract method for setting the state. See :class:`ChannelBase`
        for details.

        .. note::
            If supported, the method needs to be overwritten by a base class
            otherwise, it raises a `NotImplementedError`.
        '''
        raise NotImplementedError()

    def get_state(self):
        '''A abstract method causing a read of the state. This method should
        not return the state, but rather cause the device to read the state
        and update the appropriate instance property with the current state.

        .. note::
            If supported, the method needs to be overwritten by a base class
            otherwise, it raises a `NotImplementedError`.
        '''
        raise NotImplementedError()


class Channel(ChannelBase):
    '''Represents a device containing a single channel. E.g. a single analog
    i/o switch, a button, etc.

    For example a simple switch which does nothing::

        >>> from kivy.properties import BooleanProperty
        >>> class SimpleSwitch(Channel):
        ...     state = BooleanProperty(False, allownone=True)
        ...     def set_state(self, state):
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
    '''

    state = ObjectProperty(None, allownone=True)
    '''Represents the state of the channel.

    It is a :class:`~kivy.properties.ObjectProperty` and defaults to
    None. This variable is meant to be overwritten by device specific classes,
    e.g. a :class:`~kivy.properties.BooleanProperty` for a digital
    channel.

    .. warning::
        If :attr:`ChannelBase.reset_state` is True, then :attr:`state`, when
        overwritten with a new property must set `allownone=True`.
    '''

    def activate(self, *largs, **kwargs):
        if not self.reset_state:
            return super(Channel, self).activate(*largs, **kwargs)
        if super(Channel, self).activate(*largs, **kwargs):
            self.state = None
            return True
        return False


class Port(ChannelBase):
    '''Device similar to :class:`Channel`, except this device represents
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
    '''

    attr_map = DictProperty({})
    '''As described in :class:`Port`, each channel in the port has an
    associated property. :attr:`attr_map` maps each property to the channel it
    controls. For example, it could be the channel number in a 8-channel port,
    or a button instance. It's is up to the implementor to decide its meaning.

    In the dict, keys are the property names and values are the things they map
    to.

    :attr:`attr_map` is a :class:`~kivy.properties.DictProperty` and
    defaults to the empty dictionary.
    '''

    chan_attr_map = DictProperty({})
    '''The inverted mapping of :attr:`attr_map` and maps channels to channel
    names.

    :attr:`chan_attr_map` is a :class:`~kivy.properties.DictProperty` and
    defaults to the empty dictionary.

    .. note::
        :attr:`chan_attr_map` gets automatically updated when :attr:`attr_map`
        is changed and should therefore never be set directly.
    '''

    def __init__(self, **kwargs):
        super(Port, self).__init__(**kwargs)
        self.bind(attr_map=self._reverse_mapping)
        self._reverse_mapping()

    def _reverse_mapping(self, *largs):
        for k in self.attr_map:
            if not hasattr(self, k):
                raise AttributeError('{} is not an attribute of {}'
                                     .format(k, self))
        self.chan_attr_map = {v: k for k, v in self.attr_map.items()}

    def activate(self, *largs, **kwargs):
        if not self.reset_state:
            return super(Port, self).activate(*largs, **kwargs)
        if super(Port, self).activate(*largs, **kwargs):
            for attr in self.attr_map:
                setattr(self, attr, None)
            return True
        return False
