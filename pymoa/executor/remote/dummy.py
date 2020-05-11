"""Dummy remote executor
========================

"""
from typing import Set, Tuple
import time
import trio
import contextlib

from pymoa.executor.remote import RemoteExecutor, RemoteRegistry, \
    RemoteReferenceable, LocalRegistry
from pymoa.executor.threading import ThreadExecutor
from pymoa.executor import NO_CALLBACK


class DummyRemoteExecutor(RemoteExecutor):
    """Executor that executes the within the same thread, but creates
    duplicates of the objects and executes the methods on them.

    This can be used for testing executors in a client/server type manner.
    """

    remote_registry: RemoteRegistry = None

    local_registry: LocalRegistry = None

    use_thread_executor = False

    created_executor: Set[str] = set()

    limiter: trio.CapacityLimiter = None

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
            self, obj: 'RemoteReferenceable', *args, **kwargs):
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

    async def delete_remote_instance(self, obj: 'RemoteReferenceable'):
        hash_val = obj.hash_val
        self.local_registry.delete_instance(obj)

        # pretend we are in the remote side now
        remote_obj = self.remote_registry.delete_instance(hash_val)
        if hash_val in self.created_executor:
            self.created_executor.remove(hash_val)
            if remote_obj.executor is not None:
                await remote_obj.executor.stop_executor(block=True)

    async def start_executor(self):
        self.limiter = trio.CapacityLimiter(1)

    async def stop_executor(self, block=True):
        self.limiter = None

    async def execute(self, obj, sync_fn, args=(), kwargs=None, callback=None):
        local_registry = self.local_registry
        hash_val = obj.hash_val
        fn_name = sync_fn.__name__

        async with self.limiter:
            # pretend we are in the remote side now
            res = await self.remote_registry.call_instance_method(
                hash_val, fn_name, args, kwargs or {})

            # pretend we are now back in the calling side
            if callback is not NO_CALLBACK:
                self.call_execute_callback(obj, res, callback)
        return res

    async def get_echo_clock(self) -> Tuple[int, int, int]:
        ts = time.perf_counter_ns()
        async with self.limiter:
            t = time.perf_counter_ns()
        return ts, t, time.perf_counter_ns()

    async def get_remote_object_info(self, obj, query):
        raise NotImplementedError

    async def get_remote_objects(self):
        raise NotImplementedError

    async def apply_config_from_remote(self, obj):
        raise NotImplementedError

    async def apply_data_from_remote(self, obj):
        raise NotImplementedError

    @contextlib.asynccontextmanager
    async def get_data_from_remote(self, obj):
        raise NotImplementedError

    async def apply_execute_from_remote(
            self, obj, exclude_self=True,
            task_status=trio.TASK_STATUS_IGNORED):
        raise NotImplementedError

    @contextlib.asynccontextmanager
    async def get_execute_from_remote(self, obj):
        raise NotImplementedError
