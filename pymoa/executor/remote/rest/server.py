"""Server
=========

"""
from pymoa.executor.remote import RemoteExecutorServer, RemoteDataLogger
from pymoa.executor.threading import AsyncThreadExecutor, TrioPortal
from pymoa.executor import apply_executor

__all__ = ('RestServer', 'SSELogger')


class RestServer(RemoteExecutorServer):

    stream_objects = True

    stream_data_logs = True

    executor: AsyncThreadExecutor = None

    to_quart_thread_portal: TrioPortal = None

    def __init__(
            self, create_executor_for_obj=True,
            exec_requests_in_executor=False, stream_objects=True,
            stream_data_logs=True, **kwargs):
        super(RestServer, self).__init__(**kwargs)

        if exec_requests_in_executor:
            # post_sse_channel is called from executor thread and not from the
            # main quart thread. So we need to be able to schedule it to
            # execute back in the quart thread. todo: fix this
            self.executor = AsyncThreadExecutor(name='ServerExecutor')
            raise NotImplementedError

        self.create_executor_for_obj = create_executor_for_obj
        self.stream_objects = stream_objects
        self.stream_data_logs = stream_data_logs

        if self.stream_data_logs:
            self.stream_data_logger = SSELogger(
                sse_post_callback=self.post_sse_channel)

    async def start_executor(self):
        if self.executor:
            self.to_quart_thread_portal = TrioPortal()
            await self.executor.start_executor()

    async def stop_executor(self, block=True):
        if self.executor:
            await self.executor.stop_executor(block=block)

    @apply_executor
    async def ensure_instance(self, data: str) -> None:
        registry = self.registry
        data = self.decode(data)
        hash_val = data['hash_val']

        if hash_val in registry.hashed_instances:
            return

        obj, data = await self._create_instance(data)

        if self.stream_objects:
            channel = f'{hash_val}.ensure'
            data['channel'] = channel
            data['channel_type'] = 'ensure'
            self.post_sse_channel(data, channel, 'ensure')

    @apply_executor
    async def delete_instance(self, data: str) -> None:
        data = self.decode(data)
        hash_val = data['hash_val']

        obj, data = await self._delete_instance(data)

        if self.stream_objects:
            channel = f'{hash_val}.delete'
            data['channel'] = channel
            data['channel_type'] = 'delete'
            self.post_sse_channel(data, channel, 'delete')

    @apply_executor
    async def execute(self, data: str) -> str:
        data = self.decode(data)
        hash_val = data['hash_val']

        res, data = await self._execute(data)

        if self.stream_objects:
            channel = f'{hash_val}.execute'
            data['channel'] = channel
            data['channel_type'] = 'execute'
            self.post_sse_channel(data, channel, 'execute')

        return self.encode(res)

    def post_sse_channel(self, data, channel, channel_type):
        """Needs to be able to handle cross-thread requests.

        :param data:
        :param channel:
        :param channel_type:
        :return:
        """
        raise NotImplementedError

    @apply_executor
    async def get_object_info(self, data: str) -> str:
        """Can be one of config or data.

        :param data:
        :return:
        """
        data = self.decode(data)
        data = await self._get_object_info_data(data)
        return self.encode(data)

    async def get_echo_clock(self, data: str) -> str:
        data = self.decode(data)
        data = await self._get_clock_data(data)
        return self.encode(data)


class SSELogger(RemoteDataLogger):

    sse_post_callback = None

    def __init__(self, sse_post_callback, **kwargs):
        super(SSELogger, self).__init__(**kwargs)
        self.sse_post_callback = sse_post_callback

    def log_item(self, obj, props=None, trigger_name=None, trigger_value=None):
        data = self._get_log_item_data(obj, props, trigger_name, trigger_value)
        channel = f'{obj.hash_val}.data'
        data['channel'] = channel
        data['channel_type'] = 'data'

        self.sse_post_callback(data, channel, 'data')
