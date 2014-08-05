from kivy.config import ConfigParser as KivyConfigParser


class ConfigParser(KivyConfigParser):
    ''' Also handles 2d lists
    '''

    def set(self, section, option, value):
        if value and isinstance(value, (list, tuple)):
            if isinstance(value[0], (list, tuple)):
                value = '\n'.join([', '.join(map(str, v)) for v in value])
            else:
                value = ', '.join(map(str, value))
        return super(ConfigParser, self).set(section, option, value)
