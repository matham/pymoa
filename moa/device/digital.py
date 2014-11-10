

__all__ = ('DigitalChannel', 'DigitalPort', 'ButtonChannel', 'ButtonPort')

from kivy.properties import BooleanProperty, ObjectProperty
from moa.device.port import Channel, Port
from time import clock


class DigitalChannel(Channel):

    state = BooleanProperty(None, allownone=True)

    def set_state(self, state, **kwargs):
        pass


class DigitalPort(Port):

    def set_state(self, high=[], low=[], **kwargs):
        pass


class ButtonChannel(DigitalChannel):
    '''You can change the button's state and it'll be reflected in state.
    To change state and have it reflected in the button, you have to call
    set_state.
    '''

    button = ObjectProperty(None)

    def _update_state(self, instance, value):
        self.timestamp = clock()
        self.state = value == 'down'

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
        self.add_log(message='setting state', cause='set_state',
                     vals=('state', state))
        self.button.state = 'down' if state else 'normal'


class ButtonPort(DigitalPort):

    def _update_state(self, instance, value):
        self.timestamp = clock()
        setattr(self, self._inverse_map[instance], value == 'down')

    def activate(self, *largs, **kwargs):
        if super(ButtonPort, self).activate(*largs, **kwargs):
            for attr, button in self.mapping.items():
                button.bind(state=self._update_state)
                setattr(self, attr, button.state == 'down')
            return True
        return False

    def deactivate(self, *largs, **kwargs):
        if super(ButtonPort, self).deactivate(*largs, **kwargs):
            for button in self._inverse_map:
                button.unbind(state=self._update_state)
            return True
        return False

    def set_state(self, high=[], low=[], **kwargs):
        self.add_log(message='setting state', cause='set_state',
                     vals=('high', high, 'low', low))
        mapping = self.mapping
        for attr in high:
            mapping[attr].state = 'down'
        for attr in low:
            mapping[attr].state = 'normal'
