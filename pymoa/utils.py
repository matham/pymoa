"""Utilities
===============

"""

__all__ = ('get_class_bases', )


def get_class_bases(cls):
    """Gets all the base-classes of the class.

    :param cls:
    :return:
    """
    for base in cls.__bases__:
        if base.__name__ == 'object':
            break
        for cbase in get_class_bases(base):
            yield cbase
        yield base
