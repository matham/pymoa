'''A base class used as the base for most  Moa objects.
'''

__all__ = ('MoaBase', 'NamedMoas', 'named_moas')

from re import match, compile
from weakref import proxy
from functools import partial

from kivy.event import EventDispatcher
from kivy.properties import (
    StringProperty, DictProperty, ObjectProperty, AliasProperty)
from kivy.lang import Builder

from moa.logger import MoaObjectLogger

named_moas = None
'''Highest level of all named moas.
'''

valid_name_pat = compile('[_A-Za-z][_a-zA-Z0-9]*$')

# References to all the moa destructors (partial method with uid as key).
_moa_destructors = {}


def _moa_destructor(uid, r):
    # Internal method called when a moa object is deleted from memory. the only
    # thing we remember about it is its uid. Clear all the associated callbacks
    # created in kv language.
    del _moa_destructors[uid]
    Builder.unbind_widget(uid)


class LevelUp(object):
    pass


class NamedMoas(EventDispatcher):
    '''
    '''

    moa_parent = None

    def __getattribute__(self, name):
        val = super(NamedMoas, self).__getattribute__(name)
        if val is LevelUp:
            return getattr(self.moa_parent, name)
        return val

    def __getattr__(self, name):
        try:
            return super(NamedMoas, self).__getattr__(name)
        except AttributeError:
            if match(valid_name_pat, name) is None:
                raise
            self.create_property(name, None, rebind=True, allownone=True)
            if self.moa_parent is not None:
                setattr(self, name, LevelUp)
            return None

    def property(self, name, quiet=False):
        prop = super(NamedMoas, self).property(name, quiet=quiet)
        if prop is not None or match(valid_name_pat, name) is None:
            return prop
        self.create_property(name, None, rebind=True, allownone=True)
        if self.moa_parent is not None:
            setattr(self, name, LevelUp)
        return super(NamedMoas, self).property(name, quiet=quiet)

    def new_moas(self):
        m = NamedMoas()
        m.moa_parent = self
        return m

    def reset_attr(self, name):
        moas = self.moa_parent
        if moas is None or getattr(self, name) is not LevelUp:
            setattr(self, name, None)
        else:
            moas.reset_attr(name)


class NamedMoaBehavior(object):
    '''Should be before EventDispatcher, otherwise it eats the kwargs.
    '''

    _moas = ObjectProperty(None)

    def __init__(self, moas=None, **kwargs):
        self.moas = moas
        super(NamedMoaBehavior, self).__init__(**kwargs)

    def _get_moas(self):
        moas = self._moas
        if moas is not None:
            return moas

        parent = getattr(self, 'parent', None)
        if parent is not None:
            return getattr(parent, 'moas', named_moas)
        return named_moas

    def _set_moas(self, value):
        self._moas = value

    moas = AliasProperty(
        _get_moas, _set_moas, bind=('_moas', ), cache=False, rebind=True)


class MoaBase(MoaObjectLogger, NamedMoaBehavior, EventDispatcher):
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
    _prev_name = ''
    '''The previous name of the instance after a name change.
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
        super(MoaBase, self).__init__(**kwargs)
        if '__no_builder' not in kwargs:
            Builder.apply(self)

        # Bind all the events.
        for argument in kwargs:
            if argument[:3] == 'on_':
                self.bind(**{argument: kwargs[argument]})

        self.bind(name=self._verfiy_valid_name)  # consider doing this earlier
        self._verfiy_valid_name(self, self.name)

    def _verfiy_valid_name(self, instance, value):
        '''If it had a previous name, set it to None in
        :attr:`moa.base.named_moas`.
        Then set (and create) a property with the new name to self.
        '''
        name = self.name
        prev = self._prev_name
        named_moas = self.moas
        if prev and getattr(named_moas, prev) == self:
            named_moas.reset_attr(prev)
        self._prev_name = name
        if not name:
            return
        if match(valid_name_pat, name) is None:
            raise ValueError('"{}" is not a valid moa name. A valid '
            'name is similar to a valid Python variable name'.format(name))
        hasattr(named_moas, name)  # ensure the property with our name exists.
        setattr(named_moas, name, self.proxy_ref)

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

    name = StringProperty('')
    '''A optional name associated with this instance.

    :attr:`name` is a :kivy:class:`~kivy.properties.StringProperty` and
    defaults to `''`. If :attr:`name` is not the empty string, the :attr:`name`
    must have the same format as a valid python variable name. I.e. it cannot
    start with a number and it can only contain letters, numbers, and
    underscore.

    Whenever name is changed to a none-empty string, that name is added as an
    ObjectProperty to :attr:`moa.base.named_moas` and its value is set to
    this instance. See :attr:`moa.base.named_moas` for details.
    '''

named_moas = NamedMoas()
