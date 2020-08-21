"""Base
========

"""

__all__ = ('MoaBase', )


class MoaBase:
    """Base class for all Moa stage and device objects.

    """

    _config_props_ = ('name', )

    name: str = ''

    def __init__(self, name='', **kwargs):
        super(MoaBase, self).__init__(**kwargs)
        self.name = name
