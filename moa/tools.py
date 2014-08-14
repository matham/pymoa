
__all__ = ('to_bool', 'ConfigPropertyList')

from kivy.properties import ConfigParserProperty
from re import compile, split

to_list_pat = compile('(?:, *)?\\n?')


def to_bool(val):
    '''
    Takes anything and converts it to a bool type.
    '''
    if val == 'False' or val == '0':
        return False
    return not not val


def ConfigPropertyList(val, section, key, config, val_type, inner_list=False,
                       **kwargs):
    ''' Accepts either a list of a string. Nothing else.
    '''
    def to_list(val):
        if isinstance(val, list):
            vals = list(val)
        else:
            vals = split(to_list_pat, val.strip(' []()'))
        for i, v in enumerate(vals):
            vals[i] = val_type(v)
        return vals

    def to_2d_list(val):
        if isinstance(val, list):
            vals = list(val)
        else:
            vals = [split(to_list_pat, line.strip(' []()'))
                    for line in val.strip(' []()').splitlines()]
        for i, line in enumerate(vals):
            for j, v in enumerate(line):
                vals[i][j] = val_type(v)
        return vals

    if not isinstance(val, list):
        val = [[val]] if inner_list else [val]
    v_type = to_2d_list if inner_list else to_list
    return ConfigParserProperty(val, section, key, config, val_type=v_type,
                                **kwargs)

