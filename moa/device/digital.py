'''Digital Port
=================

Instances of :mod:`~moa.device.port` that represent Digital devices.
'''

from kivy.properties import BooleanProperty, ObjectProperty, DictProperty
from moa.device.port import Channel, Port
from time import clock

__all__ = ('DigitalChannel', 'DigitalPort', 'ButtonChannel', 'ButtonPort',
           'ButtonViewChannel', 'ButtonViewPort')


class DigitalChannel(Channel):
    '''A abstract single channel digital device.
    '''

    state = BooleanProperty(None, allownone=True)
    '''The state of the channel.

    :attr:`state` is a :class:`~kivy.properties.BooleanProperty` and
    defaults to None.
    '''

    def set_state(self, state, **kwargs):
        '''A stub method defining the prototype for :meth:`set_state` of
        derived classes.

        :Parameters:

            `state`: bool
                The value to set the state to.

        .. note::
            When called, it raises a `NotImplementedError` if not overwritten.
        '''
        raise NotImplementedError()


class DigitalPort(Port):
    '''A abstract multi-channel digital device.
    '''

    def set_state(self, high=[], low=[], **kwargs):
        '''A stub method defining the prototype for :meth:`set_state` of
        derived classes.

        For devices that support it, the properties passed in `high` and `low`
        can be set to the requested state simultaneously.

        :Parameters:

            `high`: list
                A list of the name of the properties to set to high (True)
            `low`: list
                A list of the name of the properties to set to low (False)

        .. note::
            When called, it raises a `NotImplementedError` if not overwritten.
        '''
        raise NotImplementedError()


class ButtonChannel(DigitalChannel):
    '''A device which represents the state of a Kivy
    :class:`~kivy.uix.behaviors.ButtonBehavior`.

    For example::

        >>> from kivy.uix.button import Button
        >>> class MyButton(Button):
        ...     def on_state(self, *largs):
        ...         print('Button state changed to "{}"'.format(self.state))

        >>> button = MyButton()
        >>> chan = ButtonChannel(button=button)
        >>> chan.activate(chan)
        >>> print(button.state, chan.state)
        ('normal', False)
        >>> button.state = 'down'
        Button state changed to "down"
        >>> print(button.state, chan.state)
        ('down', True)
        >>> chan.set_state(False)
        Button state changed to "normal"
        >>> print(button.state, chan.state)
        ('normal', False)
        >>> chan.deactivate(chan)
    '''

    button = ObjectProperty(None)
    '''The :class:`~kivy.uix.behaviors.ButtonBehavior` derived instance
    controlled/read by the channel.
    '''

    def _update_state(self, instance, value):
        self.timestamp = clock()
        self.state = value == 'down'
        self.dispatch('on_data_update', self)

    def activate(self, *largs, **kwargs):
        if super(ButtonChannel, self).activate(*largs, **kwargs):
            button = self.button
            button.bind(state=self._update_state)
            self.state = button.state == 'down'
            return True
        return False

    def deactivate(self, *largs, **kwargs):
        if super(ButtonChannel, self).deactivate(*largs, **kwargs):
            self.button.unbind(state=self._update_state)
            return True
        return False

    def set_state(self, state, **kwargs):
        self.button.state = 'down' if state else 'normal'


class ButtonViewChannel(DigitalChannel):
    '''Device that uses a :class:`~kivy.uix.behaviors.ButtonBehavior` type
    widget to control or reflect the state of an actual hardware device.

    :class:`ButtonViewChannel` is very similar to :class:`ButtonChannel`,
    except that for :class:`ButtonChannel` its only purpose is to have
    :attr:`~DigitalChannel.state` reflect the state of a button while for
    :class:`ButtonViewChannel` the purpose is for the button to visualize
    and control the state of an external device reflected in
    :attr:`~DigitalChannel.state`.

    That is for :class:`ButtonViewChannel`, :meth:`DigitalChannel.set_state`
    needs to be overwritten by the derived class to update the hardware
    and when the hardware changes :attr:`~DigitalChannel.state` should be
    updated. However, in addition, the button will automatically be
    updated to reflect that state and when the button's state changes
    it'll trigger a call to :meth:`DigitalChannel.set_state`.
    '''

    button = ObjectProperty(None)
    '''The :class:`~kivy.uix.behaviors.ButtonBehavior` derived instance
    controlled/read by the channel.
    '''

    def _update_from_device(self, instance, value):
        self.button.state = 'down' if self.state else 'normal'

    def _update_from_button(self, instance, value):
        if value == 'down' and not self.state:
            self.set_state(True)
        elif value == 'normal' and self.state:
            self.set_state(False)

    def activate(self, *largs, **kwargs):
        if super(ButtonViewChannel, self).activate(*largs, **kwargs):
            if 'o' in self.direction:
                button = self.button
                button.state = 'normal'
                button.fbind('state', self._update_from_button)
            self.fbind('state', self._update_from_device)
            return True
        return False

    def deactivate(self, *largs, **kwargs):
        if super(ButtonViewChannel, self).deactivate(*largs, **kwargs):
            if 'o' in self.direction:
                button = self.button
                if button is not None:
                    button.funbind('state', self._update_from_button)
                    button.state = 'normal'
            self.funbind('state', self._update_from_device)
            return True
        return False


class ButtonPort(DigitalPort):
    '''A device which represents the state of multiple Kivy
    :class:`~kivy.uix.behaviors.ButtonBehavior` buttons.

    .. note::
        For this class the values in :attr:`~moa.device.port.Port.attr_map`
        should be set to the actual buttons underlying the channels.

    For example::

        >>> from kivy.uix.button import Button
        >>> from kivy.properties import BooleanProperty

        >>> class MyButton(Button):
        ...     def on_state(self, *largs):
        ...         print("Button {}'s state changed to '{}'".format(\
self.text, self.state))

        >>> class Devs(ButtonPort):
        ...     light = BooleanProperty(None, allownone=True)
        ...     photobeam = BooleanProperty(None, allownone=True)

        >>> light = MyButton(text='Light')
        >>> beam = MyButton(text='Photobeam')
        >>> chan = Devs(attr_map={'light': light, 'photobeam': beam})
        >>> chan.activate(chan)
        >>> print(light.state, beam.state, chan.light, chan.photobeam)
        ('normal', 'normal', False, False)
        >>> light.state = 'down'
        Button Light's state changed to 'down'
        >>> print(light.state, beam.state, chan.light, chan.photobeam)
        ('down', 'normal', True, False)
        >>> chan.set_state(low=['light'], high=['photobeam'])
        Button Photobeam's state changed to 'down'
        Button Light's state changed to 'normal'
        >>> print(light.state, beam.state, chan.light, chan.photobeam)
        ('normal', 'down', False, True)
        >>> chan.deactivate(chan)
    '''

    def _update_state(self, instance, value):
        self.timestamp = clock()
        setattr(self, self.chan_attr_map[instance], value == 'down')
        self.dispatch('on_data_update', self)

    def activate(self, *largs, **kwargs):
        if super(ButtonPort, self).activate(*largs, **kwargs):
            for attr, button in self.attr_map.items():
                button.bind(state=self._update_state)
                setattr(self, attr, button.state == 'down')
            return True
        return False

    def deactivate(self, *largs, **kwargs):
        if super(ButtonPort, self).deactivate(*largs, **kwargs):
            for button in self.chan_attr_map:
                button.unbind(state=self._update_state)
            return True
        return False

    def set_state(self, high=[], low=[], **kwargs):
        attr_map = self.attr_map
        for attr in high:
            attr_map[attr].state = 'down'
        for attr in low:
            attr_map[attr].state = 'normal'


class ButtonViewPort(DigitalPort):
    '''Device that uses :class:`~kivy.uix.behaviors.ButtonBehavior` type
    widgets to control or reflect the states of an multi-channel hardware
    device.

    :class:`ButtonViewPort` is very similar to :class:`ButtonPort`,
    except that for :class:`ButtonPort` its only purpose is to have
    the port states reflect the states of the buttons while for
    :class:`ButtonViewPort` the purpose is for the buttons to visualize
    and control the states of the external device reflected in
    the properties.

    That is for :class:`ButtonViewPort`, :meth:`DigitalPort.set_state`
    needs to be overwritten by the derived class to update the hardware
    and when the hardware changes the properties should be
    updated. However, in addition, the buttons will automatically be
    updated to reflect that state and when the buttons' state changes
    it'll trigger a call to :meth:`DigitalPort.set_state`.

    .. note::
        For this class the values in :attr:`~moa.device.port.Port.attr_map`
        should be set to the buttons visualizing the channels.

        However, since this channel also controls hardware that would require
        :attr:`~moa.device.port.Port.attr_map` for mapping the property names
        to the hardware channel ports or similar, :attr:`dev_map` and
        :attr:`chan_dev_map` has been added as a secondary mapping for this
        purpose.
    '''

    dev_map = DictProperty({})
    '''A secondary mapping of property names to channel numbers etc to be used
    by the derived classes instead of :attr:`~moa.device.port.Port.attr_map`
    because :attr:`~moa.device.port.Port.attr_map` is used to map the buttons
    to property names.
    '''

    chan_dev_map = DictProperty({})
    '''The inverse mapping of :attr:`dev_map`. It is automatically
    generated and is read only.
    '''

    def __init__(self, **kwargs):
        super(ButtonViewPort, self).__init__(**kwargs)
        self.bind(dev_map=self._reverse_dev_mapping)
        self._reverse_dev_mapping()

    def _reverse_dev_mapping(self, *largs):
        for k in self.dev_map:
            if not hasattr(self, k):
                raise AttributeError('{} is not an attribute of {}'
                                     .format(k, self))
        self.chan_dev_map = {v: k for k, v in self.dev_map.items()}

    def _update_from_device(self, attr, button, instance, value):
        button.state = 'down' if getattr(self, attr) else 'normal'

    def _update_from_button(self, attr, instance, value):
        if value == 'down' and not getattr(self, attr):
            self.set_state(high=[attr])
        elif value == 'normal' and getattr(self, attr):
            self.set_state(low=[attr])

    def activate(self, *largs, **kwargs):
        if super(ButtonViewPort, self).activate(*largs, **kwargs):
            if 'o' in self.direction:
                for attr, button in self.attr_map.items():
                    button.state = 'normal'
                    button.fbind('state', self._update_from_button, attr)
            for attr, button in self.attr_map.items():
                self.fbind(attr, self._update_from_device, attr, button)
            return True
        return False

    def deactivate(self, *largs, **kwargs):
        if super(ButtonViewPort, self).deactivate(*largs, **kwargs):
            if 'o' in self.direction:
                for attr, button in self.attr_map.items():
                    button.funbind('state', self._update_from_button, attr)
                    button.state = 'normal'
            for attr, button in self.attr_map.items():
                self.funbind(attr, self._update_from_device, attr, button)
            return True
        return False
