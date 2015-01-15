'''A framework for designing and running experiments in Python using Kivy.
'''

__version__ = '0.1-dev'

from kivy import kivy_home_dir
from os import environ
from os.path import join
from moa.logger import Logger


#: moa configuration filename
moa_config_fn = ''

if not environ.get('MOA_DOC_INCLUDE'):
    moa_config_fn = join(kivy_home_dir, 'moa_config.ini')

Logger.info('Moa v%s' % (__version__))
