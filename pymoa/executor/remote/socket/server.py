"""Socket Server
================

"""

from pymoa.executor.remote import RemoteExecutorServer, RemoteDataLogger
from async_generator import aclosing

__all__ = ('SocketServer', 'StreamLogger')


class SocketServer(RemoteExecutorServer):
    """Rest server side class to handle incoming executor requests.
    """

    stream_objects = True

    stream_data_logs = True

    def __init__(self, stream_objects=True, stream_data_logs=True, **kwargs):
        super(SocketServer, self).__init__(**kwargs)

        self.stream_objects = stream_objects
        self.stream_data_logs = stream_data_logs

        if self.stream_data_logs:
            self.stream_data_logger = StreamLogger(
                stream_post_callback=self.post_stream_channel)

    def encode(self, data):
        return self.registry.encode_json_buffers(data)

    async def decode(self, data):
        raise NotImplementedError

    async def ensure_instance(self, data: dict) -> None:
        registry = self.registry
        hash_val = data['hash_val']
        if hash_val in registry.hashed_instances:
            return

        obj, data = await self._create_instance(data)

        if self.stream_objects:
            # todo: document the channels and ensure all remotes send them
            self.post_stream_channel(data, 'ensure', hash_val)

    async def delete_instance(self, data: dict) -> None:
        hash_val = data['hash_val']
        obj, data = await self._delete_instance(data)

        if self.stream_objects:
            self.post_stream_channel(data, 'delete', hash_val)

    async def execute(self, data: dict):
        hash_val = data['hash_val']
        res, data = await self._execute(data)

        if self.stream_objects:
            self.post_stream_channel(data, 'execute', hash_val)

        return res

    async def execute_generator(self, data: dict):
        # todo: limit to one socket both executes and object creation
        hash_val = data['hash_val']
        async with aclosing(self._execute_generator(data)) as aiter:
            async for res, data in aiter:
                yield res

                if self.stream_objects:
                    self.post_stream_channel(data, 'execute', hash_val)

    def post_stream_channel(self, data, channel, hash_val):
        """Needs to be able to handle cross-thread requests.

        :param data:
        :param channel:
        :param hash_val:
        :return:
        """
        raise NotImplementedError

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
