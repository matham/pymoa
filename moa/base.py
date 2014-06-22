'''
* when dispatching events, returning True stops it.
'''

__all__ = ('MoaBase', )


from weakref import ref
from kivy.event import EventDispatcher
from kivy.properties import StringProperty, OptionProperty, ObjectProperty
import logging


class MoaBase(EventDispatcher):

    named_moas = {}
    ''' A weakref.ref to the named moa instances.

    Read only.
    '''
    _last_name = ''

    def __init__(self, **kwargs):
        super(MoaBase, self).__init__(**kwargs)

        def verfiy_name(instance, value):
            named_moas = MoaBase.named_moas
            old_name = self._last_name
            if value == old_name:
                return

            if old_name:
                del named_moas[old_name]

            if value:
                if value in named_moas and named_moas[value]() is not None:
                    raise ValueError('Moa instance with name {} already '
                        'exists: {}'.format(value, named_moas[value]()))
                else:
                    named_moas[value] = ref(self)
            self._last_name = value

        self.bind(name=verfiy_name)
        verfiy_name(self, self.name)

    name = StringProperty('')
    ''' Unique name across all Moa objects
    '''

    logger = ObjectProperty(logging.getLogger('moa'),
                            baseclass=logging.Logger)

    source = StringProperty('')
    ''' E.g. a filename to load that interpreted by the subclass.
    '''
