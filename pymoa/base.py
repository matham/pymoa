"""Base
========

"""

__all__ = ('MoaBase', )


class MoaBase:

    name: str = ''

    def __init__(self, name='', **kwargs):
        super(MoaBase, self).__init__(**kwargs)
        self.name = name
