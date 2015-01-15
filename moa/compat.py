'''Modules to ease compatibility between different versions of python and
types.
'''

__all__ = ('decode_dict', 'PY2', 'unicode_type', 'bytes_type')


import sys

PY2 = sys.version_info[0] == 2
'''Whether the python version is 2.x (True), or 3.x (False).
'''


def unicode_type(val):
    ''' Converts `val` to `unicode` type. If the default encoding fails, it
    tries with `utf8`.
    '''
    try:
        return (unicode if PY2 else str)(val)
    except UnicodeDecodeError:
        return val.decode('utf8')


def bytes_type(val):
    ''' Converts `val` to `bytes` type. If the default encoding fails, it
    tries with `utf8`.
    '''
    try:
        return bytes(val)
    except UnicodeEncodeError:
        return val.encode('utf8')


def _decode_list(data):
    '''See :func:`decode_dict`.
    '''
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = _decode_list(item)
        elif isinstance(item, dict):
            item = decode_dict(item)
        rv.append(item)
    return rv


def decode_dict(data):
    '''Method which takes a dict `data` and recursively converts it keys/values
    that are unicode objects to bytes objects.

    This is typically used with json. See
    https://stackoverflow.com/questions/956867.

    E.g.::

        >>> import json
        >>>d_dump = json.dumps({'a': 55, 'b': '33', 4: {1: 'a'}, 8: ['a', 'b']})
        >>> d_dump
        '{"a": 55, "8": ["a", "b"], "b": "33", "4": {"1": "a"}}'
        >>> json.loads(d_dump)
        {u'a': 55, u'8': [u'a', u'b'], u'b': u'33', u'4': {u'1': u'a'}}
        >>> json.loads(d_dump, object_hook=decode_dict)
        {'a': 55, '8': ['a', 'b'], 'b': '33', '4': {'1': 'a'}}

    .. warning::
        Function is only python2 compatible. It is not typically required
        in py3.
    '''
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = _decode_list(value)
        elif isinstance(value, dict):
            value = decode_dict(value)
        rv[key] = value
    return rv
