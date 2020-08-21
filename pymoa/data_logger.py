"""Logger
==========

"""

import time
import csv
from os.path import exists
from typing import Iterable, List, Dict, Any, Tuple, Union, Type
import logging
from inspect import isclass
from tree_config.utils import yaml_dumps, yaml_loads

from kivy.event import EventDispatcher

from pymoa.utils import get_class_bases
from pymoa.base import MoaBase

__all__ = (
    'get_hinted_logged_names', 'ObjectLogger', 'SimpleCSVLogger',
    'SimpleTerminalLogger', 'SimpleLoggingLogger')


def get_hinted_logged_names(obj_or_cls) -> List[str]:
    cls = obj_or_cls
    if not isclass(obj_or_cls):
        cls = obj_or_cls.__class__

    hints = {}
    for c in [cls] + list(get_class_bases(cls)):
        for hint in c.__dict__.get('_logged_names_hint_', ()):
            if hint in hints:
                continue

            if not hasattr(cls, hint):
                raise Exception('Missing attribute <{}> in <{}>'.
                                format(hint, cls.__name__))
            hints[hint] = None

    return list(hints)


class ObjectLogger:
    """Logger that can hook into a :class:`Loggable` instance and log all its
    loggable properties.
    """

    logged_instances: Dict[EventDispatcher, List[Tuple[str, Any]]] = {}

    def __init__(self, **kwargs):
        super(ObjectLogger, self).__init__(**kwargs)
        self.logged_instances = {}

    def add_logged_names(
            self, obj: EventDispatcher, logged_names: Iterable[str]):
        """Can't have prop bound as trigger and as name without trigger
        (causes dups in SSELogger).

        :param obj:
        :param logged_names:
        """
        if obj in self.logged_instances:
            uids = self.logged_instances[obj]
        else:
            uids = self.logged_instances[obj] = []
        add_uid = uids.append

        fbind = obj.fbind
        for name in set(logged_names):
            if name.startswith('on_'):
                uid = fbind(name, self.log_event_callback, name)
            else:
                uid = fbind(name, self.log_property_callback, name)
            add_uid((name, uid))

    def add_trigger_logged_names(
            self, obj: EventDispatcher, trigger_names: Iterable[str],
            logged_names: Iterable[str]
    ):
        """logged_names cannot have events if trigger is not empty.

        Can't have prop bound as trigger and as name without trigger
        (causes dups in SSELogger).

        :param obj:
        :param trigger_names:
        :param logged_names:
        """
        if obj in self.logged_instances:
            uids = self.logged_instances[obj]
        else:
            uids = self.logged_instances[obj] = []
        add_uid = uids.append

        fbind = obj.fbind
        # keep sorting
        tracked_props = list({name: None for name in logged_names})
        for name in set(trigger_names):
            if name.startswith('on_'):
                uid = fbind(name, self.log_trigger_event_callback, name,
                            tracked_props)
            else:
                uid = fbind(name, self.log_trigger_property_callback, name,
                            tracked_props)
            add_uid((name, uid))

    def remove_logged_instance(self, obj: EventDispatcher):
        uids = self.logged_instances.pop(obj)
        unbind_uid = obj.unbind_uid
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

    @staticmethod
    def get_config_from_objects(
            objects: List[Union[MoaBase, EventDispatcher]],
            old_config: list = None,
            log_by_default: bool = False) -> list:
        from pymoa.stage import MoaStage
        old_config = old_config or []
        ret = []
        value = {'log': log_by_default, 'trigger': []}

        for i, obj in enumerate(objects):
            old_value = old_config[i] if i < len(old_config) else {}

            old_items = old_value.get('items', {})
            items = {name: old_items.get(name, value)
                     for name in get_hinted_logged_names(obj)}

            if isclass(obj):
                item = {'cls': obj.__name__, 'items': items}
            else:
                item = {'name': obj.name, 'cls': obj.__name__, 'items': items}

                if isinstance(obj, MoaStage) and obj.stages:
                    item['stages'] = ObjectLogger.get_config_from_objects(
                        obj.stages,
                        old_config=old_value.get('stages', None),
                        log_by_default=log_by_default)

            ret.append(item)
        return ret

    @staticmethod
    def dump_config(filename: str, config: list):
        with open(filename, 'w') as fh:
            fh.write(yaml_dumps(config))

    @staticmethod
    def load_config(filename: str) -> list:
        with open(filename) as fh:
            return yaml_loads(fh.read())

    def start_logging_from_config(
            self, objects: List[Union[MoaBase, EventDispatcher]],
            config: list) -> List[MoaBase]:
        from pymoa.stage import MoaStage
        ret_objects = set()

        for i, obj in enumerate(objects):
            if isclass(obj):
                raise TypeError(f'{obj}')

            item = config[i] if i < len(config) else {}
            if 'name' in item and item['name'] != obj.name:
                raise ValueError(f'{item["name"]} != {obj.name}')

            for name, value in item.get('items', {}).items():
                if value.get('log', False):
                    ret_objects.add(obj)
                    trigger = value.get('trigger', [])

                    if trigger:
                        self.add_trigger_logged_names(obj, [name], trigger)
                    else:
                        self.add_logged_names(obj, [name])

            if isinstance(obj, MoaStage) and obj.stages:
                ret_objects.update(self.start_logging_from_config(
                    obj.stages, item.get('stages', [])
                ))

        return list(ret_objects)


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
            ['index', 'timestamp', 'name', 'trigger', 'item', 'value'])
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

    separator = ','

    def __init__(self, separator=',', **kwargs):
        super(SimpleTerminalLogger, self).__init__(**kwargs)
        self.separator = separator

    def print_header(self):
        if self._count == -1:
            self.print_item(
                ['index', 'timestamp', 'name', 'trigger', 'item', 'value'])
            self._count = 0

    def print_item(self, item):
        print(self.separator.join(map(str, item)))

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
        getattr(logging, self.log_level)(self.separator.join(map(str, item)))
