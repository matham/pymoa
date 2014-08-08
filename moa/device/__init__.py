
from moa.base import MoaBase


class Device(MoaBase):
    ''' By default, the device does not support multi-threading.
    '''

    _activated_set = None

    def __init__(self, **kwargs):
        super(Device, self).__init__(**kwargs)
        self._activated_set = set()

    def activate(self, identifier, **kwargs):
        '''identifier is hashable.
        '''
        active = self._activated_set
        result = len(active) == 0
        active.add(identifier)
        self.add_log(message='activating device', cause='activate',
                     vals=('identifier', identifier, 'already_active',
                           not result))
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

        result = bool(old_len and not len(active))
        self.add_log(message='deactivating device', cause='deactivate',
                     vals=('identifier', identifier, 'deactivating', result))
        return result
