from typing import Set

from pymoa.executor.remote import RemoteExecutor, RemoteRegistry, \
    RemoteReferencable, LocalRegistry
from pymoa.executor.threading import ThreadExecutor
from pymoa.executor import NO_CALLBACK


class DummyRemoteExecutor(RemoteExecutor):

    remote_registry: RemoteRegistry = None

    local_registry: LocalRegistry = None

    use_thread_executor = False

    created_executor: Set[str] = set()

    def __init__(
            self, remote_registry: RemoteRegistry = None,
            local_registry: LocalRegistry = None, use_thread_executor=False,
            **kwargs):
        super(DummyRemoteExecutor, self).__init__(**kwargs)
        if remote_registry is None:
            remote_registry = RemoteRegistry()
        self.remote_registry = remote_registry

        if local_registry is None:
            local_registry = LocalRegistry()
        self.local_registry = local_registry

        self.use_thread_executor = use_thread_executor
        self.created_executor = set()

    async def ensure_remote_instance(
            self, obj: 'RemoteReferencable', *args, **kwargs):
        local_registry = self.local_registry
        config = {k: getattr(obj, k) for k in obj.config_props}
        hash_val = obj.hash_val

        mod = obj.__class__.__module__
        if mod is None:
            cls_name = obj.__class__.__qualname__
        else:
            cls_name = mod + ':' + obj.__class__.__qualname__

        local_registry.add_instance(obj)

        # pretend we are in the remote side now
        remote_registry = self.remote_registry
        if hash_val in remote_registry.hashed_instances:
            return

        remote_obj = remote_registry.create_instance(
            cls_name, args, kwargs, config)

        if self.use_thread_executor and remote_obj.executor is None:
            remote_obj.executor = ThreadExecutor()
            self.created_executor.add(remote_obj.hash_val)
            await remote_obj.executor.start_executor()

    async def delete_remote_instance(self, obj: 'RemoteReferencable'):
        hash_val = obj.hash_val
        self.local_registry.delete_instance(obj)

        # pretend we are in the remote side now
        remote_obj = self.remote_registry.delete_instance(hash_val)
        if hash_val in self.created_executor:
            self.created_executor.remove(hash_val)
            if remote_obj.executor is not None:
                await remote_obj.executor.stop_executor(block=True)

    async def start_executor(self):
        pass

    async def stop_executor(self, block=True):
        pass

    async def execute(self, obj, sync_fn, args=(), kwargs=None, callback=None):
        local_registry = self.local_registry
        hash_val = obj.hash_val
        fn_name = sync_fn.__name__

        # pretend we are in the remote side now
        res = await self.remote_registry.call_instance_method(
            hash_val, fn_name, args, kwargs or {})

        # pretend we are now back in the calling side
        self.call_execute_callback(obj, res, callback)
        return res

    async def get_remote_object_info(self, obj, query):
        raise NotImplementedError

    async def get_remote_objects(self):
        raise NotImplementedError

    async def apply_config_from_remote(self, obj):
        raise NotImplementedError

    async def apply_data_from_remote(self, obj):
        raise NotImplementedError

    async def apply_execute_from_remote(self, obj, exclude_self=True):
        raise NotImplementedError

    async def get_execute_from_remote(self, obj):
        raise NotImplementedError
