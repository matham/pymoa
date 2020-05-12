"""Quart App
============

"""
# todo: investigate compression and no-cache for data
# todo: implement back-pressure by using task-local variables for sse
from http import HTTPStatus
from quart_trio import QuartTrio
from quart import make_response, request, current_app, jsonify, websocket
from collections import defaultdict
from async_generator import aclosing
from itertools import chain
import argparse
import json

from pymoa.utils import MaxSizeSkipDeque
from pymoa.executor.remote.rest.server import RestServer
from pymoa.executor.remote.socket.server import SocketServer

import pymoa.executor.remote.referable_class_register

__all__ = ('create_app', 'QuartRestServer', 'QuartSocketServer')

MAX_QUEUE_SIZE = 20


class QuartRestServer(RestServer):
    """Quart server side rest handler.
    """

    quart_app = None

    def __init__(self, quart_app, **kwargs):
        super(QuartRestServer, self).__init__(**kwargs)
        self.quart_app = quart_app

    def post_sse_channel(self, data, channel_type, hash_val):
        post_sse_channel(self.quart_app, data, channel_type, hash_val)


class QuartSocketServer(SocketServer):
    """Quart server side socket handler.
    """

    quart_app = None

    def __init__(self, quart_app, **kwargs):
        super(QuartSocketServer, self).__init__(**kwargs)
        self.quart_app = quart_app

    async def decode(self, data):
        raise NotImplementedError

    def post_stream_channel(self, data, channel_type, hash_val):
        post_sse_channel(self.quart_app, data, channel_type, hash_val)

    def decode_json_buffers(self, data) -> dict:
        if len(data) < 16:
            raise ValueError('Unable to parse message headers')

        msg_len, json_bytes, num_buffers = \
            self.registry.decode_json_buffers_header(data[:16])

        data = data[16:]
        if len(data) != msg_len:
            raise ValueError('Unable to parse message data')

        return self.registry.decode_json_buffers(data, json_bytes, num_buffers)


def post_sse_channel(app, data, channel_type, hash_val):
    channel = f'{hash_val}.{channel_type}'

    queues = app.sse_clients[channel] if channel in app.sse_clients else {}
    queues2 = app.sse_clients[channel_type] \
        if channel_type in app.sse_clients else {}
    queues3 = app.sse_clients[hash_val] if hash_val in app.sse_clients else {}
    queues4 = app.sse_clients[''] if '' in app.sse_clients else {}

    sse_queues = list(chain(
        queues.values(), queues2.values(), queues3.values(), queues4.values()))

    if sse_queues:
        queue: MaxSizeSkipDeque
        for queue in sse_queues:
            queue.add_item((data, channel_type, hash_val, channel), 1)


async def app_init():
    current_app.sse_clients = defaultdict(dict)
    current_app.max_buffer = MAX_QUEUE_SIZE


async def ensure_instance():
    data = (await request.get_data()).decode('utf8')
    await current_app.rest_executor.ensure_instance(data)
    return '', HTTPStatus.NO_CONTENT


async def delete_instance():
    data = (await request.get_data()).decode('utf8')
    await current_app.rest_executor.delete_instance(data)
    return '', HTTPStatus.NO_CONTENT


async def execute():
    data = (await request.get_data()).decode('utf8')
    res = await current_app.rest_executor.execute(data)

    return await make_response(res, {'Content-Type': 'application/json'})


async def execute_generator():
    executor: QuartRestServer = current_app.rest_executor
    data = (await request.get_data()).decode('utf8')

    async def send_events():
        resp_data = json.dumps('alive')
        message = f"data: {resp_data}\n\n"
        yield message.encode('utf-8')

        async with aclosing(executor.execute_generator(data)) as aiter:
            async for item in aiter:
                resp_data = executor.encode({'return_value': item})
                id_data = json.dumps(False)
                message = f"data: {resp_data}\nid: {id_data}\n\n"
                yield message.encode('utf-8')

        resp_data = executor.encode({})
        id_data = json.dumps(True)
        message = f"data: {resp_data}\nid: {id_data}\n\n"
        yield message.encode('utf-8')

    response = await make_response(
        send_events(),
        {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Transfer-Encoding': 'chunked',
        },
    )
    response.timeout = None
    return response


async def get_object_info():
    data = (await request.get_data()).decode('utf8')
    res = await current_app.rest_executor.get_object_info(data)

    return await make_response(res, {'Content-Type': 'application/json'})


async def get_echo_clock():
    data = (await request.get_data()).decode('utf8')
    res = await current_app.rest_executor.get_echo_clock(data)

    return await make_response(res, {'Content-Type': 'application/json'})


async def sse():
    channel = request.args.get('channel', '')
    queue = MaxSizeSkipDeque(max_size=current_app.max_buffer)
    key = object()
    current_app.sse_clients[channel][key] = queue
    executor: QuartRestServer = current_app.rest_executor

    # todo: send alive with timeout in case skipped packets

    async def send_events():
        try:
            data = json.dumps('alive')
            message = f"data: {data}\n\n"
            yield message.encode('utf-8')

            async for (data, channel_type, hash_val, data_channel), \
                    packet in queue:
                data = executor.encode(data)
                id_data = json.dumps(
                    (packet, channel_type, hash_val, data_channel))
                message = f"data: {data}\nid: {id_data}\n\n"
                yield message.encode('utf-8')
        finally:
            del current_app.sse_clients[channel][key]
            if not current_app.sse_clients[channel]:
                del current_app.sse_clients[channel]

    response = await make_response(
        send_events(),
        {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Transfer-Encoding': 'chunked',
        },
    )
    response.timeout = None
    return response


async def websocket_handler():
    executor: QuartSocketServer = current_app.socket_executor
    await websocket.send(executor.encode({'data': 'hello'}))

    while True:
        msg = executor.decode_json_buffers(await websocket.receive())
        cmd = msg['cmd']
        packet = msg['packet']
        data = msg['data']

        ret_data = {
            'cmd': cmd,
            'packet': packet,
        }

        if cmd == 'ensure_remote_instance':
            res = await executor.ensure_instance(data)
        elif cmd == 'delete_remote_instance':
            res = await executor.delete_instance(data)
        elif cmd == 'execute':
            res = await executor.execute(data)
        elif cmd == 'execute_generator':
            ret_data['done_execute'] = False
            async with aclosing(executor.execute_generator(data)) as aiter:
                async for item in aiter:
                    ret_data['data'] = item
                    await websocket.send(executor.encode(ret_data))

            res = None
            ret_data['done_execute'] = True
        elif cmd == 'get_remote_object_info':
            res = await executor.get_object_info(data)
        elif cmd == 'get_echo_clock':
            res = await executor.get_echo_clock(data)
        else:
            raise Exception(f'Unknown command "{cmd}"')

        ret_data['data'] = res
        await websocket.send(executor.encode(ret_data))


async def websocket_stream_handler(channel):
    executor: QuartSocketServer = current_app.socket_executor
    await websocket.send(executor.encode({'data': 'hello'}))

    queue = MaxSizeSkipDeque(max_size=current_app.max_buffer)
    key = object()
    current_app.sse_clients[channel][key] = queue

    # todo: is there a timeout?

    while True:
        try:
            async for (data, channel_type, hash_val, data_channel), \
                    packet in queue:
                msg_data = {
                    'data': data,
                    'packet': packet,
                    'channel_type': channel_type,
                    'hash_val': hash_val,
                    'channel': data_channel,
                }
                await websocket.send(executor.encode(msg_data))
        finally:
            del current_app.sse_clients[channel][key]
            if not current_app.sse_clients[channel]:
                del current_app.sse_clients[channel]


async def ws():
    executor: QuartSocketServer = current_app.socket_executor
    data = executor.decode_json_buffers(await websocket.receive())
    channel = data['channel']

    if channel is None:
        await websocket_handler()
    else:
        await websocket_stream_handler(channel)


def handle_unexpected_error(error):
    message = [str(x) for x in error.args]
    status_code = 500
    success = False
    response = {
        'success': success,
        'error': {
            'type': error.__class__.__name__,
            'message': f'An unexpected error has occurred: "{message}".'
        }
    }

    return jsonify(response), status_code


def create_app() -> QuartTrio:
    """Creates the quart app.
    """
    app = QuartTrio(__name__)
    app.rest_executor = QuartRestServer(quart_app=app)
    app.socket_executor = QuartSocketServer(
        quart_app=app, registry=app.rest_executor.registry)

    app.before_first_request(app_init)

    app.add_url_rule(
        '/api/v1/objects/create_open', view_func=ensure_instance,
        methods=['POST'])
    app.add_url_rule(
        '/api/v1/objects/delete', view_func=delete_instance, methods=['POST'])
    app.add_url_rule(
        '/api/v1/objects/execute', view_func=execute, methods=['POST'])
    app.add_url_rule(
        '/api/v1/objects/execute_generator/stream',
        view_func=execute_generator, methods=['POST'])
    app.add_url_rule(
        '/api/v1/objects/object', view_func=get_object_info, methods=['GET'])
    app.add_url_rule('/api/v1/stream', view_func=sse, methods=['GET'])
    app.add_url_rule(
        '/api/v1/echo_clock', view_func=get_echo_clock, methods=['GET'])

    app.add_websocket('/api/v1/ws', view_func=ws)

    # app.register_error_handler(Exception, handle_unexpected_error)

    return app


def run_app():
    create_app().run()


if __name__ == '__main__':
    create_app().run()
