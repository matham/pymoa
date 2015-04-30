
__all__ = ('DataLogger', )


import tables as tb
from time import strftime
import moa


class DataLogger(object):

    filename = ''

    tb_file = None

    def __init__(self, filename, **kwargs):
        super(DataLogger, self).__init__(**kwargs)

        self.filename = filename
        f = self.tb_file = tb.open_file(
            filename=filename, mode='a', title='Moa log')
        attrs = f.root._v_attrs

        if 'moa_version' not in attrs:
            attrs.moa_version = moa.__version__
            attrs.original_filename = filename
            attrs.creation_time = strftime('%m-%d-%Y, %H:%M:%S')
            f.create_group(f.root, 'raw_data',
                           'Original data, timestamps, and metadat.')
