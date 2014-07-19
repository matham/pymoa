

__all__ = ('ChannelBase', 'Channel', 'Port', )

from kivy.properties import (DictProperty, BooleanProperty, NumericProperty,
                             ObjectProperty)
from moa.device import Device


class ChannelBase(Device):

    input = BooleanProperty(False)
    ''' If it contains some input channels.

    If the channels are all output channels (False) or if there are
    some input channels (True).
    '''

    timestamp = NumericProperty(0)
    ''' The time when things last updated. This is set just before the
    states are updated.
    '''

    def set_state(self, **kwargs):
        ''' Used by user to set the state.
        '''
        pass


class Channel(ChannelBase):

    state = ObjectProperty(None, allownone=True)
    ''' Meant to be overwritten.
    '''

    def activate(self, *largs, **kwargs):
        ''' Sets state to None.
        '''
        if super(Channel, self).activate(*largs, **kwargs):
            self.state = None
            return True
        return False


class Port(ChannelBase):

    mapping = DictProperty(None)
    ''' Keys are the names, values are the channel numbers, buttons etc.
    '''

    _inverse_map = {}

    def __init__(self, **kwargs):
        super(Port, self).__init__(**kwargs)
        if self.mapping is None:
            self.mapping = {}

        for k in self.mapping:
            if not hasattr(self, k):
                raise AttributeError('{} is not an attribute of {}'
                                     .format(k, self))

        def reverse_map(instance, value):
            self._inverse_map = {v: k for k, v in self.mapping.iteritems()}
        self.bind(mapping=reverse_map)
        reverse_map(self, self.mapping)

    def activate(self, *largs, **kwargs):
        ''' Activates the device, see super. It sets all the mapped attributes
        to None.
        '''
        if super(Port, self).activate(*largs, **kwargs):
            for attr in self.mapping:
                setattr(self, attr, None)
            return True
        return False
