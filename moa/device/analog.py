

__all__ = ('AnalogChannel', 'AnalogPort', 'NumericPropertyChannel',
           'NumericPropertyPort')

from kivy.properties import NumericProperty, ObjectProperty, StringProperty
from moa.device.port import Channel, Port
from functools import partial
from time import clock


class AnalogChannel(Channel):

    state = NumericProperty(0, allownone=True)

    def set_state(self, state, **kwargs):
        pass


class AnalogPort(Port):

    def set_state(self, **kwargs):
        pass


class NumericPropertyChannel(AnalogChannel):

    channel_widget = ObjectProperty(None)
    prop_name = StringProperty('')

    def _update_state(self, instance, value):
        self.timestamp = clock()
        self.state = value

    def activate(self, *largs, **kwargs):
        if super(NumericPropertyChannel, self).activate(*largs, **kwargs):
            widget = self.channel_widget
            prop = self.prop_name
            widget.bind(**{prop: self._update_state})
            self.state = getattr(widget, prop)
            return True
        return False

    def deactivate(self, *largs, **kwargs):
        if super(NumericPropertyChannel, self).deactivate(*largs, **kwargs):
            self.channel_widget.unbind(**{self.prop_name: self._update_state})
            return True
        return False

    def set_state(self, state, **kwargs):
        setattr(self.channel_widget, self.prop_name, state)


class NumericPropertyPort(AnalogPort):

    channel_widget = ObjectProperty(None)
    _widget_callbacks = []

    def _update_state(self, attr, instance, value):
        self.timestamp = clock()
        setattr(self, attr, value)

    def activate(self, *largs, **kwargs):
        if super(NumericPropertyPort, self).activate(*largs, **kwargs):
            widget = self.channel_widget
            callbacks = self._widget_callbacks = []
            f = self._update_state
            for attr, wid_attr in self.mapping.items():
                callbacks.append({wid_attr: partial(f, attr)})
                widget.bind(**callbacks[-1])
                setattr(self, attr, getattr(widget, wid_attr))
            return True
        return False

    def deactivate(self, *largs, **kwargs):
        if super(NumericPropertyPort, self).deactivate(*largs, **kwargs):
            widget = self.channel_widget
            for d in self._widget_callbacks:
                widget.unbind(**d)
            self._widget_callbacks = []
            return True
        return False

    def set_state(self, **kwargs):
        mapping = self.mapping
        widget = self.channel_widget
        for attr, value in kwargs:
            setattr(widget, mapping[attr], value)
