"""Socket Server
================

"""

from pymoa.executor.remote import RemoteExecutorServer, RemoteDataLogger
from pymoa.executor.threading import AsyncThreadExecutor
from pymoa.executor import apply_executor

__all__ = ('SocketServer', 'StreamLogger')


class SocketServer(RemoteExecutorServer):
    """Rest server side class to handle incoming executor requests.
    """

    stream_objects = True

    stream_data_logs = True

    executor: AsyncThreadExecutor = None

    def __init__(
            self, exec_requests_in_executor=False, stream_objects=True,
            stream_data_logs=True, **kwargs):
        super(SocketServer, self).__init__(**kwargs)

        if exec_requests_in_executor:
            # post_stream_channel is called from executor thread and not from
            # the main quart thread. So we need to be able to schedule it to
            # execute back in the quart thread. todo: fix this
            self.executor = AsyncThreadExecutor(name='ServerExecutor')
            raise NotImplementedError

        self.stream_objects = stream_objects
        self.stream_data_logs = stream_data_logs

        if self.stream_data_logs:
            self.stream_data_logger = StreamLogger(
                stream_post_callback=self.post_stream_channel)

    def encode(self, data):
        return self.registry.encode_json_buffers(data)

    async def decode(self, data):
        raise NotImplementedError

    async def start_executor(self):
        if self.executor:
            await self.executor.start_executor()

    async def stop_executor(self, block=True):
        if self.executor:
            await self.executor.stop_executor(block=block)

    @apply_executor
    async def ensure_instance(self, data: dict) -> None:
        registry = self.registry
        hash_val = data['hash_val']
        if hash_val in registry.hashed_instances:
            return

        obj, data = await self._create_instance(data)

        if self.stream_objects:
            self.post_stream_channel(data, 'ensure', hash_val)

    @apply_executor
    async def delete_instance(self, data: dict) -> None:
        hash_val = data['hash_val']
        obj, data = await self._delete_instance(data)

        if self.stream_objects:
            self.post_stream_channel(data, 'delete', hash_val)

    @apply_executor
    async def execute(self, data: dict):
        hash_val = data['hash_val']
        res, data = await self._execute(data)

        if self.stream_objects:
            self.post_stream_channel(data, 'execute', hash_val)

        return res

    def post_stream_channel(self, data, channel, hash_val):
        """Needs to be able to handle cross-thread requests.

        :param data:
        :param channel:
        :param hash_val:
        :return:
        """
        raise NotImplementedError

    @apply_executor
    async def get_object_info(self, data: dict):
        """Can be one of config or data.

        :param data:
        :return:
        """
        return await self._get_object_info_data(data)

    async def get_echo_clock(self, data: dict):
        return self._get_clock_data(data)


class StreamLogger(RemoteDataLogger):
    """Logs all the properties and events to the server's data stream sockets.
    """

    stream_post_callback = None

    def __init__(self, stream_post_callback, **kwargs):
        super(StreamLogger, self).__init__(**kwargs)
        self.stream_post_callback = stream_post_callback

    def log_item(self, obj, props=None, trigger_name=None, trigger_value=None):
        data = self._get_log_item_data(obj, props, trigger_name, trigger_value)
        self.stream_post_callback(data, 'data', obj.hash_val)
