'''Instances of :mod:`~moa.device.port` that represent Digital devices.
'''

__all__ = ('DigitalChannel', 'DigitalPort', 'ButtonChannel', 'ButtonPort')

from kivy.properties import BooleanProperty, ObjectProperty
from moa.device.port import Channel, Port
from time import clock


class DigitalChannel(Channel):
    '''A abstract single channel digital device.
    '''

    state = BooleanProperty(None, allownone=True)
    '''The state of the channel.

    :attr:`state` is a :kivy:class:`~kivy.properties.BooleanProperty` and
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
    :kivy:class:`~kivy.uix.behaviors.ButtonBehavior`.

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
    '''The :kivy:class:`~kivy.uix.behaviors.ButtonBehavior` derived instance
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
            self.activation = 'active'
            return True
        return False

    def deactivate(self, *largs, **kwargs):
        if super(ButtonChannel, self).deactivate(*largs, **kwargs):
            self.button.unbind(state=self._update_state)
            self.activation = 'inactive'
            return True
        return False

    def set_state(self, state, **kwargs):
        '''Sets the state of the underlying :attr:`button`. See
        :meth:`DigitalChannel.set_state` for details.
        '''
        self.button.state = 'down' if state else 'normal'


class ButtonPort(DigitalPort):
    '''A device which represents the state of multiple Kivy
    :kivy:class:`~kivy.uix.behaviors.ButtonBehavior` buttons.

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
            self.activation = 'active'
            return True
        return False

    def deactivate(self, *largs, **kwargs):
        if super(ButtonPort, self).deactivate(*largs, **kwargs):
            for button in self.chan_attr_map:
                button.unbind(state=self._update_state)
            self.activation = 'inactive'
            return True
        return False

    def set_state(self, high=[], low=[], **kwargs):
        '''Sets the state of the underlying buttons. See
        :meth:`DigitalPort.set_state` for details.
        '''
        attr_map = self.attr_map
        for attr in high:
            attr_map[attr].state = 'down'
        for attr in low:
            attr_map[attr].state = 'normal'
