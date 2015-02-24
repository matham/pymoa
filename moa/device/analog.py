'''Instances of :mod:`~moa.device.port` that represent analog input/output
devices.
'''

__all__ = ('AnalogChannel', 'AnalogPort', 'NumericPropertyChannel',
           'NumericPropertyPort')

from kivy.properties import (
    NumericProperty, ObjectProperty, StringProperty, DictProperty)
from moa.device.port import Channel, Port
from functools import partial
from time import clock


class AnalogChannel(Channel):
    '''A abstract single channel analog device.
    '''

    state = NumericProperty(None, allownone=True)
    '''The state of the channel.

    :attr:`state` is a :kivy:class:`~kivy.properties.NumericProperty` and
    defaults to None.
    '''

    def set_state(self, state, **kwargs):
        '''A stub method defining the prototype for :meth:`set_state` of
        derived classes.

        :Parameters:

            `state`: float, int
                The value to set the state to.

        .. note::
            When called, it raises a `NotImplementedError` if not overwritten.
        '''
        raise NotImplementedError()


class AnalogPort(Port):
    '''A abstract multi-channel analog device.
    '''

    def set_state(self, **kwargs):
        '''A stub method defining the prototype for :meth:`set_state` of
        derived classes.

        For devices that support it, the properties passed in one call
        can be set to the requested state simultaneously.

        Method accepts property names and their values as keyword arguments,
        where each of the properties will be set to those values.

        E.g.::

            >>> port.set_state(voltage=1.6, amp=3.7)

        .. note::
            When called, it raises a `NotImplementedError` if not overwritten.
        '''
        raise NotImplementedError()


class NumericPropertyChannel(AnalogChannel):
    '''A class that represents a analog channel by the
    :kivy:class:`~kivy.properties.NumericProperty` of a widget.

    For example::

        >>> from kivy.uix.widget import Widget
        >>> from kivy.properties import NumericProperty

        >>> class MyWidget(Widget):
        ...     value = NumericProperty(0)
        ...     def on_value(self, *largs):
        ...         print('Value changed to "{}"'.format(self.value))

        >>> widget = MyWidget()
        >>> chan = NumericPropertyChannel(channel_widget=widget, \
prop_name='value')
        >>> chan.activate(chan)
        >>> print(widget.value, chan.state)
        (0, 0)
        >>> widget.value = 5.15
        Value changed to "5.15"
        >>> print(widget.value, chan.state)
        (5.15, 5.15)
        >>> chan.set_state(3.3)
        Value changed to "3.3"
        >>> print(widget.value, chan.state)
        (3.3, 3.3)
        >>> chan.deactivate(chan)
    '''

    channel_widget = ObjectProperty(None)
    '''The widget whose :kivy:class:`~kivy.properties.NumericProperty`
    the channels is bound to.
    '''

    prop_name = StringProperty('')
    '''The name of the :kivy:class:`~kivy.properties.NumericProperty` in
    widget :attr:`channel_widget` that represents the analog channel.
    '''

    def _update_state(self, instance, value):
        self.timestamp = clock()
        self.state = value
        self.dispatch('on_data_update', self)

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
        '''Sets the value of the underlying property :attr:`prop_name`. See
        :meth:`AnalogChannel.set_state` for details.
        '''
        setattr(self.channel_widget, self.prop_name, state)


class NumericPropertyViewChannel(AnalogChannel):

    channel_widget = ObjectProperty(None)
    '''The widget whose :kivy:class:`~kivy.properties.NumericProperty`
    the channels is bound to.
    '''

    prop_name = StringProperty('')
    '''The name of the :kivy:class:`~kivy.properties.NumericProperty` in
    widget :attr:`channel_widget` that represents the analog channel.
    '''

    def _update_from_device(self, instance, value):
        setattr(self.channel_widget, self.prop_name, value)

    def _update_from_channel_widget(self, instance, value):
        if self.state != value:
            self.set_state(value)

    def activate(self, *largs, **kwargs):
        if super(NumericPropertyViewChannel, self).activate(*largs, **kwargs):
            if 'o' in self.direction:
                widget = self.channel_widget
                widget.fast_bind(
                    self.prop_name, self._update_from_channel_widget)
            self.fast_bind('state', self._update_from_device)
            return True
        return False

    def deactivate(self, *largs, **kwargs):
        if super(NumericPropertyViewChannel, self).deactivate(*largs, **kwargs):
            if 'o' in self.direction:
                widget = self.channel_widget
                if widget is not None:
                    widget.fast_unbind(
                        self.prop_name, self._update_from_channel_widget)
            self.fast_unbind('state', self._update_from_device)
            return True
        return False


class NumericPropertyPort(AnalogPort):
    '''A class that represents multiple analog channels with multiple
    :kivy:class:`~kivy.properties.NumericProperty` instances of a widget.

    .. note::
        For this class the values in :attr:`~moa.device.port.Port.attr_map`
        should be set to the names of the
        :kivy:class:`~kivy.properties.NumericProperty` instances underlying the
        channels. Similar to the single channel name
        :attr:`NumericPropertyChannel.prop_name`.

    For example::

        >>> from kivy.uix.widget import Widget
        >>> from kivy.properties import NumericProperty

        >>> class MyWidget(Widget):
        ...     voltage = NumericProperty(0)
        ...     amps = NumericProperty(0)
        ...
        ...     def on_voltage(self, *largs):
        ...         print('Voltage changed to "{}"'.format(self.voltage))
        ...
        ...     def on_amps(self, *largs):
        ...         print('Amps changed to "{}"'.format(self.amps))

        >>> class Devs(NumericPropertyPort):
        ...     voltage = NumericProperty(None, allownone=True)
        ...     amps = NumericProperty(None, allownone=True)

        >>> widget = MyWidget()
        >>> chan = Devs(channel_widget=widget, attr_map={'voltage': 'voltage',\
 'amps': 'amps'})
        >>> chan.activate(chan)
        >>> print(widget.voltage, widget.amps, chan.voltage, chan.amps)
        (0, 0, 0, 0)
        >>> widget.voltage = 5.15
        Voltage changed to "5.15"
        >>> print(widget.voltage, widget.amps, chan.voltage, chan.amps)
        (5.15, 0, 5.15, 0)
        >>> chan.set_state(voltage=3.3, amps=2.0)
        Amps changed to "2.0"
        Voltage changed to "3.3"
        >>> print(widget.voltage, widget.amps, chan.voltage, chan.amps)
        (3.3, 2.0, 3.3, 2.0)
        >>> chan.deactivate(chan)
    '''

    channel_widget = ObjectProperty(None)
    '''Similar to :attr:`NumericPropertyChannel.channel_widget`, the widget
    that contains the properties simulating the analog channels.
    '''
    _widget_callbacks = []
    '''Stores the property callbacks bound when activating the channels.
    '''

    def _update_state(self, attr, instance, value):
        self.timestamp = clock()
        setattr(self, attr, value)
        self.dispatch('on_data_update', self)

    def activate(self, *largs, **kwargs):
        if super(NumericPropertyPort, self).activate(*largs, **kwargs):
            widget = self.channel_widget
            callbacks = self._widget_callbacks = []
            f = self._update_state
            for attr, wid_attr in self.attr_map.items():
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
        '''Sets the state of the underlying properties. See
        :meth:`AnalogPort.set_state` for details.
        '''
        attr_map = self.attr_map
        widget = self.channel_widget
        for attr, value in kwargs.items():
            setattr(widget, attr_map[attr], value)


class NumericPropertyViewPort(AnalogPort):

    channel_widget = ObjectProperty(None)

    dev_map = DictProperty({})

    chan_dev_map = DictProperty({})

    def __init__(self, **kwargs):
        super(ButtonViewPort, self).__init__(**kwargs)
        self.bind(dev_map=self._reverse_dev_mapping)
        self._reverse_dev_mapping()

    def _reverse_dev_mapping(self, *largs):
        for k in self.dev_map:
            if not hasattr(self, k):
                raise AttributeError('{} is not an attribute of {}'
                                     .format(k, self))
        self.chan_dev_map = {v: k for k, v in self.dev_map.iteritems()}

    def _update_from_device(self, attr, instance, value):
        setattr(self.channel_widget, attr, value)

    def _update_from_channel_widget(self, attr, instance, value):
        if geattr(self, attr) != value:
            self.set_state(**{attr: value})

    def activate(self, *largs, **kwargs):
        if super(NumericPropertyViewPort, self).activate(*largs, **kwargs):
            if 'o' in self.direction:
                wid = self.channel_widget
                for attr, wid_attr in self.attr_map.items():
                    wid.fast_bind(
                        wid_attr, self._update_from_channel_widget, attr)
            for attr, wid_attr in self.attr_map.items():
                self.fast_bind(attr, self._update_from_device, wid_attr)
            return True
        return False

    def deactivate(self, *largs, **kwargs):
        if super(NumericPropertyViewPort, self).deactivate(*largs, **kwargs):
            if 'o' in self.direction:
                wid = self.channel_widget
                if wid is not None:
                    for attr, wid_attr in self.attr_map.items():
                        wid.fast_unbind(
                            wid_attr, self._update_from_channel_widget, attr)
            for attr, wid_attr in self.attr_map.items():
                self.fast_unbind(attr, self._update_from_device, wid_attr)
            return True
        return False
