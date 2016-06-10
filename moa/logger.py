'''Logger
==========

The Moa logger module provides a logger class that forwards logs to kivy.
It creates a base logger with name `moa` from which all moa loggers are
derived.

.. note::
    Logs that match Moa's log level are still forwarded to the kivy logger and
    emitted only if they also pass kivy's log level. Therefore, both
    the Moa and Kivy logger must be configured to the correct level for
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

import logging
from functools import partial
import sys
import os
import traceback

from kivy.logger import Logger as KivyLogger
from kivy.logger import LOG_LEVELS
from kivy.compat import PY2
from kivy.properties import (
    ObjectProperty, ListProperty, OptionProperty, StringProperty)

__all__ = ('Logger', 'MoaObjectLogger')


def logger_config_update(section, key, value):
    '''Callback called when the :attr:`~moa.config.Config` object changes the
    `log_level` key value.
    '''
    if LOG_LEVELS.get(value) is None:
        raise AttributeError('Loglevel {0!r} doesn\'t exists'.format(value))
    Logger.setLevel(level=LOG_LEVELS.get(value))


# next bit filched from logging.py
if hasattr(sys, 'frozen'):  # support for py2exe
    _srcfile = "logging%s__init__%s" % (os.sep, __file__[-4:])
elif __file__[-4:].lower() in ['.pyc', '.pyo']:
    _srcfile = __file__[:-4] + '.py'
else:
    _srcfile = __file__
_srcfile = os.path.normcase(_srcfile)


def currentframe():
    """Return the frame object for the caller's stack frame."""
    try:
        raise Exception
    except:
        return sys.exc_info()[2].tb_frame.f_back

if hasattr(sys, '_getframe'):
    def currentframe():
        return sys._getframe(3)
# done filching


class _MoaLoggerBase(logging.Logger):
    '''Moa logger class which optimizes emissions by initially checking whether
    the kivy logger is enabled for this level. This Logger is only created for
    Loggers with names that starts with `moa`.
    '''

    def isEnabledFor(self, lvl):
        if not self.name.startswith('moa'):
            return super(_MoaLoggerBase, self).isEnabledFor(lvl)
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
# logging.setLoggerClass(_orig_cls)
Logger.trace = partial(Logger.log, logging.TRACE)
_kivyhandler = KivyHandler()
_kivyhandler.setFormatter(logging.Formatter(
    '%(asctime)s %(pathname)s:%(funcName)s:%(lineno)d %(message)s'))
Logger.addHandler(_kivyhandler)


class MoaObjectLogger(object):
    '''This is a base class, which when combined with a
    :class:`~kivy.event.EventDispatcher` derived class will allow
    automatic logging of the properties and events.

    .. warning::
        This class must be combined with a
        :class:`~kivy.event.EventDispatcher` type class, otherwise it will
        raise exceptions.

    For example::

        >>> # first allow debug emissions
        >>> from moa.logger import Logger
        >>> from kivy.logger import Logger as KivyLogger
        >>> import logging
        >>> Logger.setLevel(logging.DEBUG)
        >>> KivyLogger.setLevel(logging.DEBUG)
        >>> # now we're ready
        >>> from moa.logger import MoaObjectLogger
        >>> from kivy.uix.widget import Widget
        >>> class LoggedWidget(MoaObjectLogger, Widget):
        ...     pass

        >>> wid = LoggedWidget(logged_props=['height', 'logged_props', \
'logged_pat'])
        >>> wid.height = 10
        [DEBUG             ] [Moa         ] 2015-01-30 13:06:49,184 G:\Pyth\
on\libs\Playground\src\playground8.py:<module>:10 <__main__.LoggedWidget \
object at 0x027E4228> : height=10
        >>> wid.logged_pat = '[widget wid] {}'
        [DEBUG             ] [Moa         ] 2015-01-30 13:06:49,184 \
G:\Python\libs\Playground\src\playground8.py:<module>:11 [widget wid] \
logged_pat=[widget wid] {msg}
        >>> wid.width = 10
        >>> # notice no output
        >>> wid.logged_props = ['width']
        >>> # notice no output here because the logged_* variables are changed\
 before the log output
        >>> wid.width = 50
        [DEBUG             ] [Moa         ] 2015-01-30 13:06:49,184 \
G:\Python\libs\Playground\src\playground8.py:<module>:15 [widget wid] width=50
        >>> wid.log('debug', 'hello {}', 'You')
        [DEBUG             ] [Moa         ] 2015-01-30 13:06:49,184 \
G:\Python\libs\Playground\src\playground8.py:<module>:16 [widget wid] hello You
    '''

    def __init__(self, **kwargs):
        if 'logger' not in kwargs and self.logger is None:
            self.logger = logging.getLogger(self.__module__)
        super(MoaObjectLogger, self).__init__(**kwargs)
        if self.logger is not None:
            self.fbind('logged_props', self._update_bound_loggers, 'bind')
            self.fbind(
                'logged_props_type', self._update_bound_loggers, 'bind')
            self._update_bound_loggers()

    def _update_bound_loggers(self, action='bind', *largs):
        funbind = self.funbind
        for event in self.events():
            funbind(event, self.log_event_dispatch, event)
        for prop in self.properties():
            funbind(prop, self.log_property_dispatch, prop)
        if action == 'unbind':
            return

        fbind = self.fbind
        events, props = self.events(), self.properties()
        attrs = self.logged_props
        select = self.logged_props_type
        if select == 'include':
            events = [e for e in attrs if e in events]
            props = [p for p in attrs if p in props]
        else:
            if attrs:
                events = [e for e in events if e not in attrs]
                props = [p for p in props if p not in attrs]

        for event in events:
            fbind(event, self.log_event_dispatch, event)
        for prop in props:
            fbind(prop, self.log_property_dispatch, prop)

    def log_property_dispatch(self, name, instance, value):
        '''The callback that is automatically executed when a property that is
        tracked because of :attr:`logged_props` is changed.

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
            logger.debug(
                self.logged_pat.format(msg='{}={}'.format(name, value),
                                       self=self))

    def log_event_dispatch(self, name, instance):
        '''The callback that is automatically executed when a event that is
        tracked because of :attr:`logged_props` is triggered.

        :Parameters:

            `name`: str
                The name of the event.
            `instance`: object
                The object of which the event changed (this class).
        '''
        logger = self.logger
        if logger is not None:
            logger.debug(
                self.logged_pat.format(msg='{}'.format(name), self=self))

    def log(self, level, msg, *largs, **kwargs):
        '''A convenience method that formats the message according to
        :attr:`logged_pat` and forwards it to :attr:`logger` if not None.

        It functions similar to the Logger's `log` method (largs and kwargs
        are ). See :class:`MoaObjectLogger` for an example.

        Before passing on, the log is formatted as follows::

            self.logged_pat.format(msg=msg.format(*largs, **kwargs), self=self)

        However, the keywords ``'exc_info'``, ``'extra'``, and ``'stack_info'``
        are removed from ``kwargs``, if present, and passed on to the logger's
        log method. Specifically, ``stack_info``, if True, will emit a full
        stack trace in py2 and 3.

        :Parameters:

            `level`: str
                The level of the log
            `msg`: str
                The log's message.
        '''
        logger = self.logger
        if logger is None:
            return
        logger = getattr(logger, level)

        log_kwargs = {k: kwargs.pop(k)
                      for k in ('exc_info', 'extra', 'stack_info')
                      if k in kwargs}
        msg = self.logged_pat.format(
            msg=msg.format(*largs, **kwargs), self=self)

        if PY2 and log_kwargs.pop('stack_info', False):
            msg += '\n' + ''.join(traceback.format_stack()[:-1])
        logger(msg, **log_kwargs)

    logged_props_type = OptionProperty('include', options=['exclude', 'include'])
    '''Whether the :attr:`logged_props` list indicates the properties to
    include or exclude from being logged.

    :attr:`logged_props_type` is a :class:`~kivy.properties.OptionProperty`
    and defaults to `'include'` (i.e. nothing is logged). Allowed value are
    `'exclude'` and `'include'`. See :class:`MoaObjectLogger` for details.
    '''

    logged_props = ListProperty([])
    '''A list of event and property names used to decide which events and
    properties are logged.

    If :attr:`logged_props_type` is `include`, then only properties or events in
    this list will be logged. If it's `exclude`, all properties and events,
    except those in the list, will be logged.

    :attr:`logged_props` is a :class:`~kivy.properties.ListProperty` and
    defaults to `[]`. See :class:`MoaObjectLogger` for an example.
    '''

    logged_pat = StringProperty('{self} : {msg}')
    '''The pattern used when logging to :attr:`logger`. The message logged will
    be formatted with `loagged_pat.format(msg=msg, self=self)`. `msg` is the
    message contents while self is this object whose :attr:`logger` we're
    logging to.

    :attr:`logged_pat` is a :class:`~kivy.properties.StringProperty` and
    defaults to `'{self} : {msg}'`. See :class:`MoaObjectLogger` for an
    example.
    '''

    logger = ObjectProperty(None, allownone=True)
    '''The logger object to which things are logged.

    :attr:`logger` is a :class:`~kivy.properties.ObjectProperty` and
    defaults to a Logger object with name ``__module__``, where ``__module__``
    refers to the module name of the derived class. If None, no logging will
    occur.
    '''
