'''
* when dispatching events, returning True stops it.
'''

__all__ = ('MoaBase', )


from weakref import ref
import logging
from re import match, compile
from kivy.event import EventDispatcher
from kivy.properties import StringProperty, OptionProperty, ObjectProperty
from moa.logger import Logger, LOG_LEVELS

var_pat = compile('[_A-Za-z][_a-zA-Z0-9]*$')


def pair_iterable(vals):
    for i in range(0, len(vals), 2):
            yield vals[i:i + 2]


class MoaBase(EventDispatcher):

    named_moas = {}
    ''' A weakref.ref to the named moa instances.

    Read only.
    '''
    _last_name = ''

    def __init__(self, **kwargs):
        kwargs.setdefault('logger', Logger)
        super(MoaBase, self).__init__(**kwargs)

        def verfiy_name(instance, value):
            named_moas = MoaBase.named_moas
            old_name = self._last_name
            if value == old_name:
                return

            if old_name:
                del named_moas[old_name]

            if value:
                if match(var_pat, value) is None:
                    raise ValueError('"{}" is not a valid moa name. A valid '
                    'name is similar to a python variable name'.format(value))
                if value in named_moas and named_moas[value]() is not None:
                    raise ValueError('Moa instance with name {} already '
                        'exists: {}'.format(value, named_moas[value]()))
                else:
                    named_moas[value] = ref(self)
            self._last_name = value

        self.bind(name=verfiy_name)
        verfiy_name(self, self.name)

    def add_log(self, level='debug', message='', cause='', vals=(), attrs=()):
        logger = self.logger
        if logger is None or logger.getEffectiveLevel() > LOG_LEVELS[level]:
            return
        name = self.name
        if not name:
            name = self.__class__.__name__

        f = getattr(logger, level)
        f('{},{},"{}",{}'.format(name, cause, message, ','.join(['{}: {}'.
            format(attr, val) for attr, val in tuple(pair_iterable(vals))])))
        if __debug__ and attrs:
            logger.trace('{},{} - trace,"",{}'.format(name, cause, ','.
                join(['{}: {}'.
                format(attr, getattr(self, attr)) for attr in attrs])))

    name = StringProperty('')
    ''' Unique name across all Moa objects
    '''

    logger = ObjectProperty(None, baseclass=logging.Logger, allownone=True)
