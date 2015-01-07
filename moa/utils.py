
__all__ = ('to_bool', 'ConfigPropertyList', 'ConfigPropertyDict', 'StringList',
           'String2DList', 'StringDict')

from kivy.properties import ConfigParserProperty
from re import compile, split
from copy import deepcopy

to_list_pat = compile('(?:, *)?\\n?')
to_dict_pat = compile('(?:: *)?\\n?')


def to_bool(val):
    '''
    Takes anything and converts it to a bool type.
    '''
    if val == 'False' or val == '0':
        return False
    return not not val


class StringList(list):
    def __str__(self):
        return ', '.join(map(str, self))

    def __repr__(self):
        return self.__str__()


class String2DList(list):
    def __str__(self):
        return '\n'.join([', '.join(map(str, item)) for item in self])

    def __repr__(self):
        return self.__str__()


def ConfigPropertyList(val, section, key, config, val_type, inner_list=False,
                       **kwargs):
    ''' Accepts either a list of a string. Nothing else.
    '''
    def to_list(val):
        if isinstance(val, list):
            vals = StringList(val)
        else:
            vals = StringList(split(to_list_pat, val.strip(' []()')))
        for i, v in enumerate(vals):
            vals[i] = val_type(v)
        return vals

    def to_2d_list(val):
        if isinstance(val, list):
            vals = String2DList(deepcopy(val))
        else:
            vals = String2DList([split(to_list_pat, line.strip(' []()'))
                                 for line in val.strip(' []()').splitlines()])
        for i, line in enumerate(vals):
            for j, v in enumerate(line):
                vals[i][j] = val_type(v)
        return vals

    v_type = to_2d_list if inner_list else to_list
    if not isinstance(val, list):
        val = v_type([[val]]) if inner_list else StringList([val])
    return ConfigParserProperty(val, section, key, config, val_type=v_type,
                                **kwargs)


class StringDict(dict):

    def __str__(self):
        return '\n'.join(['{}: {}'.format(k, v) for k, v in
                          sorted(self.items(), key=lambda x: x[0])])

    def __repr__(self):
        return self.__str__()


def ConfigPropertyDict(val, section, key, config, val_type, key_type,
                       **kwargs):
    ''' Accepts either a dict of a string. Nothing else.
    '''
    def to_dict(val):
        if isinstance(val, dict):
            vals = StringDict(val)
        else:
            vals = [split(to_dict_pat, line.strip(' '), maxsplit=1)
                    for line in val.strip(' }{').splitlines()]
            vals = StringDict({k: v for k, v in vals})

        return StringDict({key_type(k): val_type(v) for k, v in vals.items()})

    if not isinstance(val, dict):
        val = to_dict(val)
    return ConfigParserProperty(val, section, key, config, val_type=to_dict,
                                **kwargs)
