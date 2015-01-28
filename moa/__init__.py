'''A framework for designing and running experiments in Python using Kivy.

:Environment:

    `MOA_CLOCK`:
        When `'1'`, the :func:`~moa.clock.set_clock` will be called and
        set to the :class:`~moa.clock.MoaClockBase` before anything else is
        imported.
'''

__version__ = '0.1-dev'

from kivy import kivy_home_dir
from os import environ
from os.path import join

if environ.get('MOA_CLOCK', '0') in ('1', 'True'):
    from moa.clock import set_clock
    set_clock(clock='moa')

from moa.logger import Logger


#: moa configuration filename
moa_config_fn = ''

if not environ.get('MOA_DOC_INCLUDE'):
    moa_config_fn = join(kivy_home_dir, 'moa_config.ini')

Logger.info('Moa v%s' % (__version__))
