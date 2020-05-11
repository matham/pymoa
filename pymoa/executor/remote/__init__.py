"""Remote
=========

Import ``pymoa.executor.remote.referable_class_register`` to automatically
register device classes with the InstanceRegistry so that it could be created
remotely.

"""
from typing import Dict, List, Any, Callable, Tuple, Set, AsyncGenerator, \
    Iterable
import contextlib
import json
from trio import TASK_STATUS_IGNORED
import base64
import hashlib
import uuid
import struct
from itertools import accumulate
from functools import partial
import time

from pymoa.data_logger import Loggable, ObjectLogger
from pymoa.executor import Executor
from pymoa.executor.threading import ThreadExecutor
from pymoa.utils import get_class_bases

__all__ = (
    'RemoteExecutorBase', 'RemoteExecutor', 'RemoteExecutorServerBase',
    'RemoteExecutorServer', 'RemoteDataLogger', 'RemoteReferenceable',
    'InstanceRegistry', 'RemoteRegistry', 'LocalRegistry')


class RemoteExecutorBase(Executor):
    """Base class for executors that execute the methods on remote objects,
    rather than within process.
    """

    async def ensure_remote_instance(
            self, obj: 'RemoteReferenceable', *args, **kwargs):
        raise NotImplementedError

    async def delete_remote_instance(self, obj: 'RemoteReferenceable'):
        raise NotImplementedError

    async def get_remote_object_info(self, obj, query):
        """

        :param obj:
        :param query: Can be one of config or data.
        :return:
        """
        raise NotImplementedError

    async def get_remote_objects(self):
        raise NotImplementedError

    async def apply_config_from_remote(self, obj):
        raise NotImplementedError

    async def apply_data_from_remote(
            self, obj, task_status=TASK_STATUS_IGNORED):
        raise NotImplementedError

    @contextlib.asynccontextmanager
    async def get_data_from_remote(
            self, obj, task_status=TASK_STATUS_IGNORED):
        raise NotImplementedError

    async def apply_execute_from_remote(
            self, obj, exclude_self=True, task_status=TASK_STATUS_IGNORED):
        raise NotImplementedError

    @contextlib.asynccontextmanager
    async def get_execute_from_remote(
            self, obj, task_status=TASK_STATUS_IGNORED) -> AsyncGenerator:
        raise NotImplementedError

    def encode(self, data):
        raise NotImplementedError

    def decode(self, data):
        raise NotImplementedError


class RemoteExecutor(RemoteExecutorBase):
    """Concrete executor that will execute objects remotely."""

    registry: 'LocalRegistry' = None

    _uuid: bytes = None

    def __init__(self, registry: 'LocalRegistry' = None, **kwargs):
        super(RemoteExecutor, self).__init__(**kwargs)
        if registry is None:
            registry = LocalRegistry()
        self.registry = registry
        self._uuid = uuid.uuid4().bytes

    def encode(self, data):
        return self.registry.encode_json(data)

    def decode(self, data):
        return self.registry.decode_json(data)

    def _get_ensure_remote_instance_data(
            self, obj: 'RemoteReferenceable', args, kwargs):
        # todo: handle specifying remote executor for this instance
        # todo: add root executor method to create instance and
        #  call that remotely auto
        config = {k: getattr(obj, k) for k in obj.config_props}
        mod = obj.__class__.__module__
        if mod is None:
            cls_name = obj.__class__.__qualname__
        else:
            cls_name = mod + ':' + obj.__class__.__qualname__
        hash_val = obj.hash_val

        data = {
            'cls_name': cls_name,
            'args': args,
            'kwargs': kwargs,
            'config': config,
            'hash_val': hash_val,
        }
        return data

    def _get_delete_remote_instance_data(self, obj: 'RemoteReferenceable'):
        return {'hash_val': obj.hash_val}

    def _get_execute_data(
            self, obj, sync_fn, args=(), kwargs=None, callback=None):
        hash_val = obj.hash_val
        fn_name = sync_fn.__name__
        cb_name = callback
        if cb_name is not None:
            if not isinstance(cb_name, str):
                cb_name = cb_name.__name__

        data = {
            'hash_val': hash_val,
            'method_name': fn_name,
            'args': args,
            'kwargs': kwargs or {},
            'callback': cb_name,
            'uuid': self._uuid,
        }
        return data

    def _get_remote_object_info_data(self, obj, query):
        return {'hash_val': obj.hash_val if obj else None, 'query': query}

    def _apply_config_from_remote(self, obj, data):
        for key, value in data.items():
            setattr(obj, key, value)

    async def _apply_data_from_remote(self, obj, gen):
        async for data in gen:
            trigger_name = data['logged_trigger_name']
            trigger_value = data['logged_trigger_value']
            props = data['logged_items']

            for key, value in props.items():
                if key.startswith('on_'):
                    obj.dispatch(key, obj, *value)
                else:
                    setattr(obj, key, value)

            if trigger_name:
                if trigger_name.startswith('on_'):
                    obj.dispatch(trigger_name, *trigger_value)
                else:
                    setattr(obj, trigger_name, trigger_value)

    async def _apply_execute_from_remote(self, obj, gen, exclude_self):
        uuid = self._uuid
        if exclude_self and uuid is None:
            raise ValueError('Cannot exclude self when uuid is not set')

        async for data in gen:
            callback = data['callback']
            return_value = data['return_value']

            if exclude_self and uuid == data['uuid']:
                continue

            self.call_execute_callback(obj, return_value, callback)

    def _get_clock_data(self) -> dict:
        return {}


class RemoteExecutorServerBase:
    """Base class for the server side handling of remote object method
    execution.
    """

    async def ensure_instance(self, *args, **kwargs):
        raise NotImplementedError

    async def delete_instance(self, *args, **kwargs):
        raise NotImplementedError

    async def execute(self, *args, **kwargs):
        raise NotImplementedError

    async def get_object_info(self, *args, **kwargs):
        raise NotImplementedError

    def encode(self, data):
        raise NotImplementedError

    def decode(self, data):
        raise NotImplementedError


class RemoteExecutorServer(RemoteExecutorServerBase):
    """Concrete server side handler of remote object method execution.
    """

    registry: 'RemoteRegistry' = None

    create_executor_for_obj = True

    created_executor: Set[str] = set()

    stream_data_logger: 'RemoteDataLogger' = None

    def __init__(self, registry: 'RemoteRegistry' = None,
                 create_executor_for_obj=True, **kwargs):
        super(RemoteExecutorServer, self).__init__(**kwargs)
        if registry is None:
            registry = RemoteRegistry()
        self.registry = registry

        self.create_executor_for_obj = create_executor_for_obj
        self.created_executor = set()

    def encode(self, data):
        return self.registry.encode_json(data)

    def decode(self, data):
        return self.registry.decode_json(data)

    async def _create_instance(
            self, data: dict) -> ('RemoteReferenceable', dict):
        hash_val = data['hash_val']
        cls_name = data['cls_name']
        args = data['args']
        kwargs = data['kwargs']
        config = data['config']
        obj = self.registry.create_instance(cls_name, args, kwargs, config)

        if self.create_executor_for_obj and obj.executor is None:
            obj.executor = ThreadExecutor()
            self.created_executor.add(obj.hash_val)
            await obj.executor.start_executor()

        if self.stream_data_logger is not None:
            self.stream_data_logger.add_logged_instance(obj)

        return obj, data

    async def _delete_instance(
            self, data: dict) -> ('RemoteReferenceable', dict):
        hash_val = data['hash_val']
        obj = self.registry.delete_instance(hash_val)

        if self.stream_data_logger is not None:
            self.stream_data_logger.remove_logged_instance(obj)

        if hash_val in self.created_executor:
            self.created_executor.remove(hash_val)
            if obj.executor is not None:
                await obj.executor.stop_executor(block=False)  # TODO: block?

        return obj, data

    async def _execute(self, data: dict) -> (Any, dict):
        hash_val = data['hash_val']
        method_name = data['method_name']
        args = data['args']
        kwargs = data['kwargs']
        callback = data['callback']

        res = await self.registry.call_instance_method(
            hash_val, method_name, args, kwargs)
        data['return_value'] = res

        return res, data

    async def _get_object_info_data(self, data: dict) -> dict:
        """

        :param hash_val:
        :param query: Can be one of config or data.
        :return:
        """
        hash_val = data['hash_val']
        query = data['query']
        registry = self.registry
        obj = registry.hashed_instances[hash_val] if hash_val else None
        if query == 'config':
            if obj:
                data = {k: getattr(obj, k) for k in obj.config_props}
            else:
                data = [{k: getattr(o, k) for k in o.config_props}
                        for o in registry.hashed_instances.values()]
        elif query == 'data':
            data = {k: getattr(obj, k) for k in obj.logged_names
                    if not k.startswith('on_')}
        else:
            raise ValueError(f'Unrecognized query {query}')

        return data

    def _get_clock_data(self, data: dict) -> dict:
        return {'server_time': time.perf_counter_ns()}


class RemoteDataLogger(ObjectLogger):
    """Data logger used to log all data updates and stream it to clients.
    """

    def _get_log_item_data(self, obj, props, trigger_name, trigger_value):
        data = {
            'logged_trigger_name': trigger_name,
            'logged_trigger_value': trigger_value,
            'logged_items': props or {},
            'hash_val': obj.hash_val,
        }
        return data

    def log_item(self, obj, props=None, trigger_name=None, trigger_value=None):
        raise NotImplementedError

    def log_property_callback(self, name, obj, value):
        self.log_item(obj, props={name: value})

    def log_event_callback(self, name, obj, *args):
        self.log_item(obj, props={name: args})

    def log_trigger_property_callback(self, name, tracked_props, obj, value):
        props = {k: getattr(obj, k) for k in tracked_props if k != name}
        self.log_item(obj, trigger_name=name, trigger_value=value, props=props)

    def log_trigger_event_callback(self, name, tracked_props, obj, *args):
        props = {k: getattr(obj, k) for k in tracked_props}
        self.log_item(obj, trigger_name=name, trigger_value=args, props=props)


class InstanceRegistry:
    """Registry that contains objects know by the register that can be
    referenced.
    """

    referenceable_classes: Dict[str, Callable] = {}

    hashed_instances: Dict[str, 'RemoteReferenceable'] = {}

    json_coders: Dict[str, Tuple[type, Callable, Callable]] = {}

    def __init__(self, **kwargs):
        super(InstanceRegistry, self).__init__(**kwargs)
        self.hashed_instances = {}

    @classmethod
    def register_class(cls, class_to_register: type):
        mod = class_to_register.__module__
        if mod is None:
            cls_name = class_to_register.__qualname__
        else:
            cls_name = mod + ':' + class_to_register.__qualname__

        cls.referenceable_classes[cls_name] = class_to_register

    @classmethod
    def register_json_coder(
            cls, name: str, class_to_register: type, encoder: Callable,
            decoder: Callable):
        cls.json_coders[f'__@@{name}'] = class_to_register, encoder, decoder

    def referenceable_json_decoder(self, dct: dict, buffers: list = None):
        if len(dct) != 1:
            return dct

        (name, value), = dct.items()
        if '__@@remote_object' == name:
            return self.hashed_instances[value]
        if '__@@base64' == name:
            return base64.standard_b64decode(value)
        if '__@@buff' == name:
            return buffers[value]

        json_coders = self.json_coders
        if name in json_coders:
            decoder = json_coders[name][2]
            return decoder(value)
        return dct

    def decode_json(self, data: str):
        return json.loads(data, object_hook=self.referenceable_json_decoder)

    def decode_json_buffers_header(self, header: bytes):
        magic, msg_len, json_bytes, num_buffers = struct.unpack('!4I', header)
        if magic != 0xc33f0f68:
            raise ValueError(f'Stream corrupted. Magic number {magic} '
                             f'doe not match 0xc33f0f68')
        return msg_len, json_bytes, num_buffers

    def decode_json_buffers(
            self, data: bytes, json_bytes: int, num_buffers: int):
        json_msg = data[:json_bytes].decode('utf8')
        buffer_lengths = struct.unpack(
            f'!{num_buffers}I',
            data[json_bytes: json_bytes + num_buffers * 4]
        )
        buff_flat = data[json_bytes + num_buffers * 4:]

        indices = [0] + list(accumulate(buffer_lengths))
        buffers = [buff_flat[s:e] for s, e in zip(indices[:-1], indices[1:])]

        decoder = partial(self.referenceable_json_decoder, buffers=buffers)
        return json.loads(json_msg, object_hook=decoder)

    def encode_json_func(self, obj, buffers: list = None):
        if isinstance(obj, RemoteReferenceable):
            return {'__@@remote_object': obj.hash_val}
        if isinstance(obj, (bytes, bytearray)):
            if buffers is None:
                data = base64.standard_b64encode(obj).decode('ascii')
                return {'__@@base64': data}

            i = len(buffers)
            buffers.append(obj)
            return {'__@@buff': i}

        for name, (cls, encoder, _) in self.json_coders.items():
            if isinstance(obj, cls):
                return {name: encoder(obj)}

        raise TypeError(f'Object of type {obj.__class__.__name__} '
                        f'is not JSON serializable')

    def encode_json(self, obj) -> str:
        return json.dumps(obj, default=self.encode_json_func)

    def prepare_json_buffers(self, obj) -> Tuple[bytes, List[bytes]]:
        buffers = []
        s = json.dumps(
            obj, default=partial(self.encode_json_func, buffers=buffers))
        return s.encode('utf8'), buffers

    def encode_json_buffers(self, obj) -> bytes:
        """Message is: magic number, size of dynamic message, size of json,
        number of buffers, json, list of size for each buffer, buffers.
        """
        json_bytes, buffers = self.prepare_json_buffers(obj)

        lengths = list(map(len, buffers))
        var_msg_len = sum(lengths) + len(json_bytes) + len(buffers) * 4

        header = struct.pack(
            '!4I', 0xc33f0f68, var_msg_len, len(json_bytes), len(lengths))
        encoded_lengths = struct.pack(f'!{len(lengths)}I', *lengths)

        return b''.join([header, json_bytes, encoded_lengths] + buffers)


class RemoteRegistry(InstanceRegistry):
    """Server side object registry.
    """

    def create_instance(
            self, cls_name: str, args: tuple, kwargs: dict, config: dict
    ) -> 'RemoteReferenceable':

        obj = self.referenceable_classes[cls_name](*args, **kwargs)
        for name, value in config.items():
            setattr(obj, name, value)
        self.hashed_instances[obj.hash_val] = obj
        return obj

    def delete_instance(self, obj_hash: str) -> 'RemoteReferenceable':
        return self.hashed_instances.pop(obj_hash)

    async def call_instance_method(
            self, obj_hash: str, method_name: str, args: tuple, kwargs: dict
    ) -> Any:
        func = getattr(self.hashed_instances[obj_hash], method_name)
        return await func(*args, **kwargs)


class LocalRegistry(InstanceRegistry):
    """Client side object registry.
    """

    def add_instance(self, obj: 'RemoteReferenceable'):
        self.hashed_instances[obj.hash_val] = obj

    def delete_instance(self, obj: 'RemoteReferenceable'):
        del self.hashed_instances[obj.hash_val]


class ReferenceableMetaclass(type):

    def __new__(mcs, *args, **kwargs):
        cls = super().__new__(mcs, *args, **kwargs)
        InstanceRegistry.register_class(cls)
        return cls


class RemoteReferenceable(Loggable, metaclass=ReferenceableMetaclass):
    """Base class for objects that can be referenced remotely.
    """

    _config_props_: Tuple[str] = ('name', )

    executor: Executor = None

    _hash_val: str = None

    _config_props: List[str] = None

    def __init__(self, executor: Executor = None, **kwargs):
        super(RemoteReferenceable, self).__init__(**kwargs)
        self.executor = executor

    @property
    def hash_val(self) -> str:
        hash_val = self._hash_val
        if hash_val is not None:
            return hash_val

        cls = self.__class__
        mod = cls.__module__
        if mod is None:
            cls_name = cls.__qualname__
        else:
            cls_name = mod + ':' + cls.__qualname__

        props = {'__cls': cls_name, 'name': self.name}

        m = hashlib.md5()
        m.update(json.dumps(props, sort_keys=True).encode('utf8'))
        hash_val = self._hash_val = m.hexdigest()
        return hash_val

    @property
    def config_props(self) -> List[str]:
        props = self._config_props
        if props is None:
            props = set()
            cls = self.__class__

            for c in [cls] + list(get_class_bases(cls)):
                if '_config_props_' not in c.__dict__:
                    continue

                for prop in c._config_props_:
                    if prop in props:
                        continue

                    if not hasattr(cls, prop):
                        raise Exception('Missing attribute <{}> in <{}>'.
                                        format(prop, cls.__name__))
                    props.add(prop)

            self._config_props = props = list(props)

        return props
