

__all__ = ('DigitalGate', 'DigitalPort')

from kivy.properties import DictProperty, BooleanProperty
from moa.device import Device
import re


class DigitalGate(Device):

    state = BooleanProperty(False)

    def set_state(self, **kwargs):
        ''' Used by user to set the state.
        '''
        pass


class DigitalPort(Device):

    mapping = DictProperty({})
    ''' Keys are the names, values are the channel numbers.
    '''
    _inverse_map = {}

    def __init__(self, mapping={}, **kwargs):
        super(DigitalPort, self).__init__(**kwargs)
        pat = re.compile('[_A-Za-z][_a-zA-Z0-9]*$')
        match = re.match

        for k, v in mapping.iteritems():
            if hasattr(self, k):
                raise Exception('{} already has a attribute named {}'
                                .format(self, k))
            if match(pat, k) is None:
                raise Exception('{} is not a valid python identifier'
                                .format(k))
            self.setattrself.create_property(k, False)

        def reverse_map(instance, value):
            self._inverse_map = {v: k for k, v in self.mapping.iteritems()}
        self.bind(mapping=reverse_map)
        reverse_map(self, self.mapping)

    def refresh_state(self, state_list=None, state_int=None):
        ''' Internal method
        '''
        if state_list is not None:
            for k, v in self.mapping.iteritems():
                setattr(self, k, state_list[v])
        if state_int is not None:
            for k, v in self.mapping.iteritems():
                setattr(self, k, bool(state_int & (1 << v)))

    def set_state(self, **kwargs):
        pass
