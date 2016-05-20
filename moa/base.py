'''A base class used as the base for most  Moa objects.
'''

from re import match, compile
from weakref import proxy
from functools import partial

from kivy.event import EventDispatcher
from kivy.properties import (
    StringProperty, DictProperty, ObjectProperty, AliasProperty)
from kivy.lang import Builder
from kivy.uix.behaviors.knspace import KNSpaceBehavior, knspace
from moa.logger import MoaObjectLogger

__all__ = ('MoaBase', )

knspace.keep_ref = True

valid_name_pat = compile('[_A-Za-z][_a-zA-Z0-9]*$')

# References to all the moa destructors (partial method with uid as key).
_moa_destructors = {}


def _moa_destructor(uid, r):
    # Internal method called when a moa object is deleted from memory. the only
    # thing we remember about it is its uid. Clear all the associated callbacks
    # created in kv language.
    del _moa_destructors[uid]
    Builder.unbind_widget(uid)


class MoaBase(MoaObjectLogger, KNSpaceBehavior, EventDispatcher):
    '''The class that is the base of many Moa classes and provides the required
    kivy properties and logging mechanisms.

    Similar to :kivy:class:`~kivy.uix.widget.Widget`, each instance has a
    property called `__self__` which points to the real `self`. When holding
    a :attr:`proxy_ref`, one can call `instance.__self__` to get the underlying
    instance. This is useful in the kv language, where references typically
    use the :attr:`proxy_ref`.
    '''

    _proxy_ref = None
    '''See :attr:`MoaBase.proxy_ref`.
    '''
    id = ''
    '''Similar to :kivy:attr:`~kivy.uix.widget.Widget.id`, the name of the
    instance when used from kv with a name.
    '''
    cls = []
    '''Similar to :kivy:attr:`~kivy.uix.widget.Widget.cls`, except it is not
    currently used and remains here for kv compatibility.
    '''

    ids = DictProperty({})

    def __init__(self, **kwargs):
        builder = '__no_builder' not in kwargs
        kwargs.pop('__no_builder', None)
        super(MoaBase, self).__init__(**kwargs)
        if builder:
            Builder.apply(self)

        # Bind all the events.
        for argument in kwargs:
            if argument[:3] == 'on_':
                self.bind(**{argument: kwargs[argument]})

        self.bind(knsname=self._verfiy_valid_name)
        self._verfiy_valid_name(self, self.knsname)

    def _verfiy_valid_name(self, instance, value):
        '''If it had a previous name, set it to None in
        :attr:`moa.base.named_moas`.
        Then set (and create) a property with the new name to self.
        '''
        if not value:
            return
        if match(valid_name_pat, value) is None:
            raise ValueError('"{}" is not a valid moa namespace name. A valid '
            'name is similar to a valid Python variable name'.format(value))

    @property
    def proxy_ref(self):
        '''Return a proxy reference to the moa instance. The proxy gets created
        lazily on first use. It is required by the kv language.
         See `weakref.proxy
        <http://docs.python.org/2/library/weakref.html?highlight\
        =proxy#weakref.proxy>`_ for more information.
        '''
        _proxy_ref = self._proxy_ref
        if _proxy_ref is not None:
            return _proxy_ref

        f = partial(_moa_destructor, self.uid)
        self._proxy_ref = _proxy_ref = proxy(self, f)
        _moa_destructors[self.uid] = (f, _proxy_ref)
        return _proxy_ref

    def __eq__(self, other):
        if not isinstance(other, MoaBase):
            return False
        return self.proxy_ref is other.proxy_ref

    def __hash__(self):
        return id(self)

    @property
    def __self__(self):
        return self

    name = StringProperty('')  # for backwards compat
