"""Logger
==========

"""
import time
import csv
from os.path import exists
from typing import Iterable, List, Dict, Any, Tuple
from itertools import chain
import logging

from kivy.event import EventDispatcher

from pymoa.utils import get_class_bases
from pymoa.base import MoaBase

__all__ = (
    'Loggable', 'ObjectLogger', 'SimpleCSVLogger', 'SimpleTerminalLogger',
    'SimpleLoggingLogger')


class Loggable(EventDispatcher, MoaBase):
    """Base class for devices that support logging its properties or events.
    """

    _logged_names_: Tuple[str] = ()

    _logged_trigger_names_: Tuple[str] = ()

    _logged_names: List[str] = None

    @property
    def logged_names(self) -> List[str]:
        names = self._logged_names
        if names is None:
            names = set()
            cls = self.__class__

            for c in [cls] + list(get_class_bases(cls)):
                if '_logged_names_' not in c.__dict__:
                    continue

                for prop in c._logged_names_:
                    if prop in names:
                        continue

                    if not hasattr(cls, prop):
                        raise Exception('Missing attribute <{}> in <{}>'.
                                        format(prop, cls.__name__))
                    names.add(prop)

            self._logged_names = names = list(names)

        return names

    _logged_trigger_names: List[str] = None

    @property
    def logged_trigger_names(self) -> List[str]:
        names = self._logged_trigger_names
        if names is None:
            names = set()
            cls = self.__class__

            for c in [cls] + list(get_class_bases(cls)):
                if '_logged_trigger_names_' not in c.__dict__:
                    continue

                for prop in c._logged_trigger_names_:
                    if prop in names:
                        continue

                    if not hasattr(cls, prop):
                        raise Exception('Missing attribute <{}> in <{}>'.
                                        format(prop, cls.__name__))
                    names.add(prop)

            self._logged_trigger_names = names = list(names)

        return names


class ObjectLogger:
    """Logger that can hook into a :class:`Loggable` instance and log all its
    loggable properties.
    """

    logged_instances: Dict[Loggable, List[Tuple[str, Any]]] = {}

    def __init__(self, **kwargs):
        super(ObjectLogger, self).__init__(**kwargs)
        self.logged_instances = {}

    def add_logged_instance(
            self, loggable: Loggable,
            triggered_names: Iterable[str] = (),
            logged_names: Iterable[str] = (),
            use_default_logged_names: bool = True,
            use_default_logged_trigger_names: bool = True,
    ):
        """logged_names cannot have events if trigger is not empty.

        Can't have prop bound as trigger and as name without trigger
        (causes dups in SSELogger).

        :param loggable:
        :param triggered_names:
        :param logged_names:
        :param use_default_logged_names:
        :param use_default_logged_trigger_names:
        :return:
        """
        if loggable in self.logged_instances:
            uids = self.logged_instances[loggable]
        else:
            uids = self.logged_instances[loggable] = []
        add_uid = uids.append

        default_triggered_names = []
        if use_default_logged_trigger_names:
            default_triggered_names = loggable.logged_trigger_names

        default_logged_names = []
        if use_default_logged_names:
            default_logged_names = loggable.logged_names

        fbind = loggable.fbind
        if not triggered_names and not default_triggered_names:
            for name in set(chain(default_logged_names, logged_names)):
                if name.startswith('on_'):
                    uid = fbind(name, self.log_event_callback, name)
                else:
                    uid = fbind(name, self.log_property_callback, name)
                add_uid((name, uid))
        else:
            tracked_props = set(chain(default_logged_names, logged_names))
            for name in set(chain(default_triggered_names, triggered_names)):
                if name.startswith('on_'):
                    uid = fbind(name, self.log_trigger_event_callback, name,
                                tracked_props)
                else:
                    uid = fbind(name, self.log_trigger_property_callback, name,
                                tracked_props)
                add_uid((name, uid))

    def remove_logged_instance(self, loggable: Loggable):
        uids = self.logged_instances.pop(loggable)
        unbind_uid = loggable.unbind_uid
        for name, uid in uids:
            unbind_uid(name, uid)

    def log_property_callback(self, name, obj, value):
        raise NotImplementedError

    def log_event_callback(self, name, obj, *args):
        raise NotImplementedError

    def log_trigger_property_callback(self, name, tracked_props, obj, value):
        raise NotImplementedError

    def log_trigger_event_callback(self, name, tracked_props, obj, *args):
        raise NotImplementedError


class SimpleCSVLogger(ObjectLogger):
    """Concrete implementation of :class:`ObjectLogger` that logs to a csv
    file.
    """

    filename: str = ''

    _file_descriptor = None

    _csv_writer: csv.writer = None

    _count = 0

    def __init__(self, filename, **kwargs):
        super(SimpleCSVLogger, self).__init__(**kwargs)
        self.filename = filename

    def __enter__(self):
        self.open_file()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_file()
        return False

    def open_file(self):
        if self._file_descriptor is not None:
            raise TypeError('File is already open')
        if exists(self.filename):
            raise ValueError(f'"{self.filename}" already exists')
        self._file_descriptor = open(self.filename, mode='w', newline='')
        writer = self._csv_writer = csv.writer(self._file_descriptor)
        writer.writerow(
            ['count', 'timestamp', 'name', 'trigger', 'item', 'value'])
        self._count = 0

    def close_file(self):
        if self._file_descriptor is None:
            return
        self._file_descriptor.close()
        self._file_descriptor = None
        self._csv_writer = None

    def log_property_callback(self, name, obj, value):
        self._csv_writer.writerow(
            map(str, [
                self._count, time.perf_counter(), obj.name, '', name, value]))
        self._count += 1

    def log_event_callback(self, name, obj, *args):
        self._csv_writer.writerow(
            map(str, [
                self._count, time.perf_counter(), obj.name, '', name, '']))
        self._count += 1

    def log_trigger_property_callback(self, name, tracked_props, obj, value):
        i = self._count
        t = time.perf_counter()
        obj_name = obj.name
        writerow = self._csv_writer.writerow

        for prop in tracked_props:
            writerow(
                map(str, [i, t, obj_name, name, prop, getattr(obj, prop)]))
        self._count += 1

    def log_trigger_event_callback(self, name, tracked_props, obj, *args):
        i = self._count
        t = time.perf_counter()
        obj_name = obj.name
        writerow = self._csv_writer.writerow

        for prop in tracked_props:
            writerow(
                map(str, [i, t, obj_name, name, prop, getattr(obj, prop)]))
        self._count += 1


class SimpleTerminalLogger(ObjectLogger):
    """Concrete implementation of :class:`ObjectLogger` that logs to the
    terminal by printing.
    """

    _count = -1

    def print_header(self):
        if self._count == -1:
            self.print_item(
                ['count', 'timestamp', 'name', 'trigger', 'item', 'value'])
            self._count = 0

    def print_item(self, item):
        print('\t'.join(map(str, item)))

    def log_property_callback(self, name, obj, value):
        self.print_header()
        self.print_item([
            self._count, time.perf_counter(), obj.name, '', name, value])
        self._count += 1

    def log_event_callback(self, name, obj, *args):
        self.print_header()
        self.print_item([
            self._count, time.perf_counter(), obj.name, '', name, ''])
        self._count += 1

    def log_trigger_property_callback(self, name, tracked_props, obj, value):
        self.print_header()
        i = self._count
        t = time.perf_counter()
        obj_name = obj.name

        for prop in tracked_props:
            self.print_item([
                i, t, obj_name, name, prop, getattr(obj, prop)])
        self._count += 1

    def log_trigger_event_callback(self, name, tracked_props, obj, *args):
        self.print_header()
        i = self._count
        t = time.perf_counter()
        obj_name = obj.name

        for prop in tracked_props:
            self.print_item([
                i, t, obj_name, name, prop, getattr(obj, prop)])
        self._count += 1


class SimpleLoggingLogger(SimpleTerminalLogger):
    """Concrete implementation of :class:`ObjectLogger` that logs to the
    python's logging system.
    """

    log_level = 'warning'

    def print_item(self, item):
        getattr(logging, self.log_level)('\t'.join(map(str, item)))
