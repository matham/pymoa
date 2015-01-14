'''A base class used as the base for most  Moa objects.
'''

__all__ = ('MoaBase', )

from re import match, compile
from kivy.event import EventDispatcher
from kivy.properties import StringProperty
from moa.logger import MoaObjectLogger

valid_name_pat = compile('[_A-Za-z][_a-zA-Z0-9]*$')


class MoaBase(MoaObjectLogger, EventDispatcher):

    def __init__(self, **kwargs):
        super(MoaBase, self).__init__(**kwargs)
        self.bind(name=self._verfiy_valid_name)
        self._verfiy_valid_name(self, self.name)

    def _verfiy_valid_name(self, instance, value):
        if value and match(valid_name_pat, value) is None:
            raise ValueError('"{}" is not a valid moa name. A valid '
            'name is similar to a python variable name'.format(value))


    name = StringProperty('')
    '''A optional name associated with this instance.

    :attr:`name` is a :kivy:class:`~kivy.properties.StringProperty` and
    defaults to `''`. If :attr:`name` is not the empty string, the :attr:`name`
    must have the same format as a valid python variable name. I.e. it cannot
    start with a number and it can only contain letters, numbers, and
    underscore.
    '''
