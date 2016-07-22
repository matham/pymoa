'''Moa
=======
A framework for designing and running experiments in Python using Kivy.

.. note::

    :mod:`moa` needs to be imported before anything clock related in kivy
    is imported.

'''

from os import environ
from os.path import join

if 'KIVY_CLOCK' not in environ:
    environ['KIVY_CLOCK'] = 'free_only'

from kivy import kivy_home_dir

from moa.logger import Logger

__version__ = '0.1'


#: moa configuration filename
moa_config_fn = ''

if not environ.get('KIVY_DOC_INCLUDE'):
    moa_config_fn = join(kivy_home_dir, 'moa_config.ini')

Logger.info('Moa v%s' % (__version__))
