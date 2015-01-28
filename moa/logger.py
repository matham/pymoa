'''The Moa logger module provides a logger class that is forwarded to kivy.
It creates a base logger with name `moa` from which all moa logger are derived.

.. note::
    Logs that pass the filter and are emitted by the moa logger, are forwarded
    to the kivy logger and emitted based on kivy's log level. Therefore, both
    the moa and kivy logger must be configured to the correct level for
    emission.

For example::

    >>> from kivy.logger import Logger as KivyLogger
    >>> from moa.logger import Logger
    >>> import logging

    >>> KivyLogger.setLevel(logging.INFO)
    >>> Logger.setLevel(logging.DEBUG)
    >>> Logger.debug('debug hello')
    >>> Logger.info('info hello')
    [INFO              ] [Moa         ] 2015-01-14 14:34:49,936 moa.<module>:8\
 info hello
    >>> KivyLogger.setLevel(logging.DEBUG)
    >>> Logger.debug('debug hello')
    [DEBUG             ] [Moa         ] 2015-01-14 14:34:49,937 moa.<module>:\
10 debug hello
'''

__all__ = ('Logger', 'MoaObjectLogger')

from kivy.logger import Logger as KivyLogger
from kivy.logger import LOG_LEVELS

from kivy.properties import (
    ObjectProperty, ListProperty, OptionProperty, StringProperty)
import logging
from functools import partial


def logger_config_update(section, key, value):
    '''Callback called when the :attr:`~moa.config.Config` object changes the
    `log_level` key value.
    '''
    if LOG_LEVELS.get(value) is None:
        raise AttributeError('Loglevel {0!r} doesn\'t exists'.format(value))
    Logger.setLevel(level=LOG_LEVELS.get(value))


class _MoaLoggerBase(logging.Logger):
    '''Moa logger class which optimizes emissions by initially checking whether
    the kivy logger is enabled for this level.
    '''

    def isEnabledFor(self, lvl):
        if super(_MoaLoggerBase, self).isEnabledFor(lvl):
            return KivyLogger.isEnabledFor(lvl)
        return False


class KivyHandler(logging.Handler):
    '''The Moa handler class that forwards logs to kivy.
    '''

    def emit(self, record):
        if KivyLogger.isEnabledFor(record.levelno):
            KivyLogger.log(
                record.levelno, 'Moa: {}'.format(self.format(record)))

_orig_cls = logging.getLoggerClass()
logging.setLoggerClass(_MoaLoggerBase)
Logger = logging.getLogger('moa')
'''The `moa` logger instance.
'''
logging.setLoggerClass(_orig_cls)
Logger.trace = partial(Logger.log, logging.TRACE)
_kivyhandler = KivyHandler()
_kivyhandler.setFormatter(logging.Formatter(
    '%(asctime)s %(name)s.%(funcName)s:%(lineno)d %(message)s'))
Logger.addHandler(_kivyhandler)


class MoaObjectLogger(object):
    '''This is a base class, which when combined with a
    :kivy:class:`~kivy.event.EventDispatcher` derived class will allow
    automatic logging of the properties and events.

    .. warning::
        This calls must be combined with a
        :kivy:class:`~kivy.event.EventDispatcher` type class, otherwise it will
        raise exceptions.

    For example::

        >>> from moa.logger import MoaObjectLogger
        >>> from kivy.uix.widget import Widget
        >>> class LoggedWidget(MoaObjectLogger, Widget):
        ...     pass

        >>> wid = LoggedWidget(logged_attrs=['height', 'logged_attrs', \
'logged_pat'])
        >>> wid.height = 10
        [DEBUG             ] [Moa         ] 2015-01-14 15:35:17,918 moa.logge\
r.log_property_dispatch:138 height=10
        >>> wid.logged_pat = '[widget wid] {}'
        [DEBUG             ] [Moa         ] 2015-01-14 15:35:17,918 moa.logger\
.log_property_dispatch:138 [widget wid] logged_pat=[widget wid] {}
        >>> wid.width = 10
        >>> # notice no output
        >>> wid.logged_attrs = ['width']
        >>> # notice no output here because the logged_* variables are changed\
 before the log output
        >>> wid.width = 50
        [DEBUG             ] [Moa         ] 2015-01-14 15:35:17,918 moa.logger\
.log_property_dispatch:138 [widget wid] width=50
        >>> wid.log('debug', 'hello {}', 'You')
        [DEBUG             ] [Moa         ] 2015-01-14 16:34:41,226 moa.logger\
.log:183 [widget wid] hello You

    '''

    def __init__(self, **kwargs):
        super(MoaObjectLogger, self).__init__(**kwargs)
        if self.logger is not None:
            self.fast_bind('logged_attrs', self._update_bound_loggers, 'bind')
            self.fast_bind(
                'log_attrs_type', self._update_bound_loggers, 'bind')
            self._update_bound_loggers()

    def _update_bound_loggers(self, action='bind', *largs):
        fast_unbind = self.fast_unbind
        for event in self.events():
            fast_unbind(event, self.log_event_dispatch, event)
        for prop in self.properties():
            fast_unbind(prop, self.log_property_dispatch, prop)
        if action == 'unbind':
            return

        fast_bind = self.fast_bind
        events, props = self.events(), self.properties()
        attrs = self.logged_attrs
        select = self.log_attrs_type
        if select == 'include':
            events = [e for e in attrs if e in events]
            props = [p for p in attrs if p in props]
        else:
            if attrs:
                events = [e for e in events if e not in attrs]
                props = [p for p in props if p not in attrs]

        for event in events:
            fast_bind(event, self.log_event_dispatch, event)
        for prop in props:
            fast_bind(prop, self.log_property_dispatch, prop)

    def log_property_dispatch(self, name, instance, value):
        '''The callback that is executed when a property is changed.

        :Parameters:

            `name`: str
                The name of the event.
            `instance`: object
                The object of which the event changed (this class).
            `value`: object
                The new value taken by property `name`.
        '''
        logger = self.logger
        if logger is not None:
            logger.debug(self.logged_pat.format('{}={}'.format(name, value)))

    def log_event_dispatch(self, name, instance):
        '''The callback that is executed when a event is triggered.

        :Parameters:

            `name`: str
                The name of the event.
            `instance`: object
                The object of which the event changed (this class).
        '''
        logger = self.logger
        if logger is not None:
            logger.debug(self.logged_pat.format('{}'.format(name)))

    def log(self, level, msg, *largs, **kwargs):
        '''A convenience method that formats the message according to
        :attr:`logged_pat` and forwards it to :attr:`logger` if not None.
        It functions similar to the Logger's `log` method (largs and kwargs
        are ). See :class:`MoaObjectLogger` for an example.
        '''
        logger = self.logger
        if logger is None:
            return
        getattr(logger, level)(self.logged_pat.format(
            msg.format(*largs, **kwargs)))

    log_attrs_type = OptionProperty('include', options=['exclude', 'include'])
    '''Whether the :attr:`logged_attrs` list indicates the properties and to
    include or exclude from being logged.

    :attr:`log_attrs_type` is a :kivy:class:`~kivy.properties.OptionProperty`
    and defaults to `'include'` (i.e. nothing is logged). Allowed value are
    `'exclude'` and `'include'`. See :class:`MoaObjectLogger` for details.
    '''

    logged_attrs = ListProperty([])
    '''A list of event and property names used to decide which events and
    properties are logged.

    If :attr:`log_attrs_type` is `include`, then only properties or events in
    this list will be logged. If it's `exclude`, all properties and events,
    except those in the list, will be logged.

    :attr:`logged_attrs` is a :kivy:class:`~kivy.properties.ListProperty` and
    defaults to `[]`. See :class:`MoaObjectLogger` for an example.
    '''

    logged_pat = StringProperty('{}')
    '''The pattern used when logging to :attr:`logger`. The message will be
    added with format on the string. Therefore, if it contains a `'{}'`, it'll
    be replaced with the message.

    :attr:`logged_pat` is a :kivy:class:`~kivy.properties.StringProperty` and
    defaults to `'{}'`. See :class:`MoaObjectLogger` for an example.
    '''

    logger = ObjectProperty(logging.getLogger(__name__), allownone=True)
    '''The logger object to which things are logged.

    :attr:`logger` is a :kivy:class:`~kivy.properties.ObjectProperty` and
    defaults to a Logger object with name `__name__`. If None, no logging will
    occur.
    '''
