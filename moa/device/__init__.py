
from moa.base import MoaBase


class Device(MoaBase):
    ''' By default, the device does not support multi-threading.
    '''

    _activated_set = None

    def __init__(self, **kwargs):
        super(Device, self).__init__(**kwargs)
        self._activated_set = set()

    def activate(self, identifier, **kwargs):
        active = self._activated_set
        result = len(active) == 0
        active.add(identifier)
        return result

    def recover(self, **kwargs):
        pass

    def deactivate(self, identifier, clear=False, **kwargs):
        active = self._activated_set
        old_len = len(active)

        if clear:
            active.clear()
        else:
            try:
                active.remove(identifier)
            except KeyError:
                pass

        return bool(old_len and not len(active))
