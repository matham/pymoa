

__all__ = ('decode_dict', 'PY2', 'unicode_type', 'bytes_type')


import sys

PY2 = sys.version_info[0] == 2


def unicode_type(val):
    ''' Converts to `unicode` type.
    '''
    try:
        return (unicode if PY2 else str)(val)
    except UnicodeDecodeError:
        return val.decode('utf8')


def bytes_type(val):
    ''' Converts to `bytes`.
    '''
    try:
        return bytes(val)
    except UnicodeEncodeError:
        return val.encode('utf8')


# from https://stackoverflow.com/questions/956867
def _decode_list(data):
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
    ''' Only python2 compatibale.
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
