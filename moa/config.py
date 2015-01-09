'''Config module based on the kivy :kivy:class:`~kivy.config.ConfigParser`.
'''

__all__ = ('ConfigParser', )

from kivy.config import ConfigParser as KivyConfigParser


class ConfigParser(KivyConfigParser):
    '''Config parser class. Currently it's identical to
    :kivy:class:`~kivy.config.ConfigParser`.
    '''
    pass
