
from moa.base import MoaBase


class Device(MoaBase):
    ''' By default, the device does not support multi-threading.
    '''

    def activate(self, **kwargs):
        pass

    def recover(self, **kwargs):
        pass

    def deactivate(self, **kwargs):
        pass
