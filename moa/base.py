'''
* when dispatching events, returning True stops it.
'''


from kivy.event import EventDispatcher
from kivy.properties import StringProperty, OptionProperty


class MoaException(Exception):
    pass


class MoaBase(EventDispatcher):

    _widgets = {}
    _name = ''

    @staticmethod
    def get_named_instance(name):
        return MoaBase._widgets[name]

    def __init__(self, **kwargs):
        self.size_hint = None, None
        self.size = 0, 0
        super(MoaBase, self).__init__(**kwargs)

        self.bind(name=self._verfiy_name)

    def _verfiy_name(self, instance, value):
        widgets = MoaBase._widgets
        old_name = self._name
        if value == old_name:
            return

        if value and value in widgets:
            raise ValueError('Moa instance with name {} already exists, {}'.
                             format(value, widgets[value]))
        if old_name:
            del widgets[old_name]
        if value:
            widgets[value] = self
        self._name = value

    name = StringProperty('')
    ''' Unique name across all Moa objects
    '''
    log_level = OptionProperty('debug', options=['debug', 'info', 'critical',
                                                 'quiet'])
    ''' How much to log, in addition to whatever the class saves.
    '''
    source = StringProperty('')
    ''' E.g. a filename to load that interpreted by the subclass.
    '''
