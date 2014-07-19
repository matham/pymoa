
__all__ = ('to_bool', 'ConfigPropertyList')

from kivy.properties import ConfigParserProperty
from re import compile, split
from functools import partial

to_list_pat = compile(', *')


def to_bool(val):
    '''
    Takes anything and converts it to a bool type.
    '''
    if val == 'False':
        return False
    return not not val


def ConfigPropertyList(val, section, key, config, val_type, **kwargs):
    def to_list(val):
        if isinstance(val, list):
            vals = val
        else:
            vals = split(to_list_pat, val.strip(' []()'))
        for i, v in enumerate(vals):
            vals[i] = val_type(v)
        return vals

    if not isinstance(val, list):
        val = [val]
    return ConfigParserProperty(val, section, key, config, val_type=to_list,
                                **kwargs)

