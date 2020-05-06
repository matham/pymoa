"""Remote
=========

"""
from typing import Dict, List, Any, Callable, Iterable, Tuple, Set, AsyncGenerator
import json
import base64
import hashlib
import time

from pymoa.data_logger import Loggable, ObjectLogger
from pymoa.executor import Executor
from pymoa.executor.threading import ThreadExecutor
from pymoa.utils import get_class_bases

__all__ = (
    'RemoteExecutorBase', 'RemoteExecutor', 'RemoteExecutorServerBase',
    'RemoteExecutorServer',
    'RemoteDataLogger', 'RemoteReferencable', 'InstanceRegistry',
    'RemoteRegistry', 'LocalRegistry')


class RemoteExecutorBase(Executor):

    async def ensure_remote_instance(
            self, obj: 'RemoteReferencable', *args, **kwargs):
        raise NotImplementedError

    async def delete_remote_instance(self, obj: 'RemoteReferencable'):
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

    async def apply_data_from_remote(self, obj):
        raise NotImplementedError

    async def get_data_from_remote(self, obj):
        raise NotImplementedError

    async def apply_execute_from_remote(self, obj, exclude_self=True):
        raise NotImplementedError

    async def get_execute_from_remote(self, obj) -> AsyncGenerator:
        raise NotImplementedError

    def encode(self, data):
        raise NotImplementedError

    def decode(self, data):
        raise NotImplementedError


class RemoteExecutor(RemoteExecutorBase):

    registry: 'LocalRegistry' = None

    _uuid: bytes = None

    def __init__(self, registry: 'LocalRegistry' = None, **kwargs):
        super(RemoteExecutor, self).__init__(**kwargs)
        if registry is None:
            registry = LocalRegistry()
        self.registry = registry

    def encode(self, data):
        return self.registry.encode_json(data)

    def decode(self, data):
        return self.registry.decode_json(data)

    def _get_ensure_remote_instance_data(
            self, obj: 'RemoteReferencable', args, kwargs):
        # TODO: handle specifying remote executor for this instance
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

    def _get_delete_remote_instance_data(self, obj: 'RemoteReferencable'):
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

    async def _get_clock_data(self) -> dict:
        return {}


class RemoteExecutorServerBase:

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

    registry: 'RemoteRegistry' = None

    create_executor_for_obj = False

    created_executor: Set[str] = set()

    stream_data_logger: 'RemoteDataLogger' = None

    def __init__(self, registry: 'RemoteRegistry' = None,  **kwargs):
        super(RemoteExecutorServer, self).__init__(**kwargs)
        if registry is None:
            registry = RemoteRegistry()
        self.registry = registry

        self.created_executor = set()

    def encode(self, data):
        return self.registry.encode_json(data)

    def decode(self, data):
        return self.registry.decode_json(data)

    async def _create_instance(
            self, data: dict) -> ('RemoteReferencable', dict):
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
            self, data: dict) -> ('RemoteReferencable', dict):
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

    async def _get_clock_data(self, data: dict) -> dict:
        return {'server_time': time.perf_counter_ns()}


class RemoteDataLogger(ObjectLogger):

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

    referencable_classes: Dict[str, Callable] = {}

    hashed_instances: Dict[str, 'RemoteReferencable'] = {}

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

        cls.referencable_classes[cls_name] = class_to_register

    @classmethod
    def register_json_coder(
            cls, name: str, class_to_register: type, encoder: Callable,
            decoder: Callable):
        cls.json_coders[f'@{name}'] = class_to_register, encoder, decoder

    def referencable_json_decoder(self, dct: dict):
        if len(dct) != 1:
            return dct

        (name, value), = dct.items()
        if '@remote_object' == name:
            return self.hashed_instances[value]
        if '@base64' == name:
            return base64.standard_b64decode(value)

        json_coders = self.json_coders
        if name in json_coders:
            decoder = json_coders[name][2]
            return decoder(value)
        return dct

    def decode_json(self, data: str, default: Any = None):
        if data:
            return json.loads(data, object_hook=self.referencable_json_decoder)
        return default

    def encode_json_func(self, obj):
        if isinstance(obj, RemoteReferencable):
            return {'@remote_object': obj.hash_val}
        if isinstance(obj, (bytes, bytearray)):
            data = base64.standard_b64encode(obj).decode('ascii')
            return {'@base64': data}

        for name, (cls, encoder, _) in self.json_coders.items():
            if isinstance(obj, cls):
                return {name: encoder(obj)}

        raise TypeError(f'Object of type {obj.__class__.__name__} ' 
                        f'is not JSON serializable')

    def encode_json(self, obj):
        return json.dumps(obj, default=self.encode_json_func)


class RemoteRegistry(InstanceRegistry):

    def create_instance(
            self, cls_name: str, args: tuple, kwargs: dict, config: dict
    ) -> 'RemoteReferencable':

        obj = self.referencable_classes[cls_name](*args, **kwargs)
        for name, value in config.items():
            setattr(obj, name, value)
        self.hashed_instances[obj.hash_val] = obj
        return obj

    def delete_instance(self, obj_hash: str) -> 'RemoteReferencable':
        return self.hashed_instances.pop(obj_hash)

    async def call_instance_method(
            self, obj_hash: str, method_name: str, args: tuple, kwargs: dict
    ) -> Any:
        func = getattr(self.hashed_instances[obj_hash], method_name)
        return await func(*args, **kwargs)


class LocalRegistry(InstanceRegistry):

    def add_instance(self, obj: 'RemoteReferencable'):
        self.hashed_instances[obj.hash_val] = obj

    def delete_instance(self, obj: 'RemoteReferencable'):
        del self.hashed_instances[obj.hash_val]


class ReferencableMetaclass(type):

    def __new__(mcs, *args, **kwargs):
        cls = super().__new__(mcs, *args, **kwargs)
        InstanceRegistry.register_class(cls)
        return cls


class RemoteReferencable(Loggable, metaclass=ReferencableMetaclass):

    _config_props_: Tuple[str] = ('name', )

    executor: Executor = None

    _hash_val: str = None

    _config_props: List[str] = None

    def __init__(self, executor: Executor = None, **kwargs):
        super(RemoteReferencable, self).__init__(**kwargs)
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
