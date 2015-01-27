'''Config module based on the kivy :kivy:class:`~kivy.config.ConfigParser`.
It defines a :attr:`Config` class used to configure Moa.
'''

__all__ = ('Config', 'ConfigParser')

from os import environ
from os.path import isfile

from kivy.config import ConfigParser as KivyConfigParser

from moa.logger import logger_config_update
from moa import moa_config_fn

# Version number of current configuration format
MOA_CONFIG_VERSION = 0

Config = None
'''Moa configuration object. Its kivy::attr:`~kivy.config.ConfigParser.name` is
`'moa'`.

The config file named `moa_config.ini` is placed in the same home directory as
the kivy `config.ini` file.

Available configuration tokens
------------------------------

:moa:

    `log_level`: string, one of 'debug', 'info', 'warning', 'error' or \
'critical'
        Set the minimum log level to use.
'''


class ConfigParser(KivyConfigParser):
    '''Config parser class. Currently it is identical to
    :kivy:class:`~kivy.config.ConfigParser`.
    '''
    pass


if not environ.get('MOA_DOC_INCLUDE'):
    # Create default configuration
    Config = ConfigParser(name='moa')
    Config.add_callback(logger_config_update, 'moa', 'log_level')

    # Read config file if exist
    if (isfile(moa_config_fn) and
            'MOA_USE_DEFAULTCONFIG' not in environ and
            'MOA_NO_CONFIG' not in environ):
        try:
            Config.read(moa_config_fn)
        except Exception as e:
            Logger.exception('Core: error while reading local configuration')

    version = Config.getdefaultint('moa', 'config_version', 0)

    # Add defaults section
    Config.adddefaultsection('moa')

    # Upgrade default configuration until we have the current version
    need_save = False
    if version != MOA_CONFIG_VERSION and 'MOA_NO_CONFIG' not in environ:
        Logger.warning('Config: Older configuration version detected'
                       ' ({0} instead of {1})'.format(
                           version, MOA_CONFIG_VERSION))
        Logger.warning('Config: Upgrading configuration in progress.')
        need_save = True

    while version < MOA_CONFIG_VERSION:
        Logger.debug('Config: Upgrading from %d to %d' %
                     (version, version + 1))

        if version == 0:

            # log level
            Config.setdefault('moa', 'log_level', 'info')

        #elif version == 1:
        #   # add here the command for upgrading from configuration 0 to 1
        #
        else:
            # for future.
            break

        # Pass to the next version
        version += 1

    # Indicate to the Config that we've upgrade to the latest version.
    Config.set('moa', 'config_version', MOA_CONFIG_VERSION)

    # If no configuration exist, write the default one.
    if ((not isfile(moa_config_fn) or need_save) and
            'MOA_NO_CONFIG' not in environ):
        try:
            Config.filename = moa_config_fn
            Config.write()
        except Exception as e:
            Logger.exception('Core: Error while saving default config file')
