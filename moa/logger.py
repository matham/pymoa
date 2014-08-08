

__all__ = ('Logger', 'LOG_LEVELS')


import logging
import os
from os.path import exists, join
from time import strftime
from functools import partial
from moa.compat import PY2

_filehandler = Logger = None
logging.TRACE = 9
LOG_LEVELS = {
    'trace': logging.TRACE,
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL}



def set_logfile(filepath, filename):
    ''' `%_` parts of `filename` will be replaced with a number (if exists)
    creating a unique filename. Then, the filename will be passed to
    `strftime`.
    '''
    if not os.path.isdir(filepath):
        os.makedirs(filepath)
    pattern = join(filepath, strftime(filename.replace('%_', '@@NUMBER@@')))

    n = 0
    while True:
        filename = pattern.replace('@@NUMBER@@', str(n))
        if not exists(filename):
            break
        n += 1
        if n > 10000:  # prevent maybe flooding ?
            raise Exception('Too many logfile, remove some')

    if _filehandler.filename == filename:
            return
    _filehandler.filename = filename
    if _filehandler.fd is not None:
        _filehandler.fd.close()
    _filehandler.fd = open(filename, 'w')

    Logger.info('Logger: Record log in %s' % filename)


class FileHandler(logging.Handler):
    filename = ''
    fd = None

    def emit(self, record):
        fd = self.fd
        if fd is None:
            return

        fd.write('[%-18s] ' % record.levelname)
        try:
            fd.write(record.msg)
        except UnicodeEncodeError:
            if PY2:
                fd.write(record.msg.encode('utf8'))
        fd.write('\n')
        fd.flush()


Logger = logging.getLogger('moa')
Logger.trace = partial(Logger.log, logging.TRACE)
_filehandler = FileHandler()
Logger.addHandler(_filehandler)
Logger.addHandler(logging.StreamHandler())
