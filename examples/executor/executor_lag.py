
import trio
import time

from pymoa.executor.remote.app.quart import create_app
from pymoa.executor.remote.rest.client import RestExecutor
from pymoa.executor.threading import ThreadExecutor, AsyncThreadExecutor
from pymoa.executor.remote.dummy import DummyRemoteExecutor
from pymoa.device.analog import RandomAnalogChannel
from pymoa.executor.remote.socket.websocket_client import WebSocketExecutor


async def measure_within_process_quart_lag(cls):
    app = create_app()
    async with trio.open_nursery() as socket_nursery:
        if cls is RestExecutor:
            executor = RestExecutor(uri='http://127.0.0.1:5001')
        else:
            executor = WebSocketExecutor(
                nursery=socket_nursery, server='127.0.0.1', port=5001)

        device = RandomAnalogChannel(executor=executor)
        requests = []
        responses = []

        async with trio.open_nursery() as nursery:
            nursery.start_soon(app.run_task, "127.0.0.1", 5001)
            await trio.sleep(1)

            async with app.app_context():
                await executor.start_executor()

                for _ in range(100):
                    ts, t, te = await executor.get_echo_clock()
                    requests.append((t - ts) / 1e6)
                    responses.append((te - t) / 1e6)

                await executor.ensure_remote_instance(device)
                ts = time.perf_counter_ns()
                for _ in range(100):
                    await device.read_state()
                te = time.perf_counter_ns()

                await device.pump_state(100)
                rate_cont = 100 * 1e9 / (time.perf_counter_ns() - te)

                await executor.delete_remote_instance(device)
                await executor.stop_executor(block=True)

            nursery.cancel_scope.cancel()

    request = sum(requests) / len(requests)
    response = sum(responses) / len(responses)
    print(f'Quart-internal - {cls.__name__}; Request lag: {request:.2f}ms. '
          f'Response lag: {response:.2f}ms. '
          f'Rate: {100 * 1e9 / (te - ts):.2f}Hz. '
          f'Continuous rate: {rate_cont:.2f}Hz')


async def measure_outside_process_quart_lag(cls, host='127.0.0.1', port=5000):
    async with trio.open_nursery() as socket_nursery:
        if cls is RestExecutor:
            executor = RestExecutor(uri=f'http://{host}:{port}')
        else:
            executor = WebSocketExecutor(
                nursery=socket_nursery, server=host, port=port)

        device = RandomAnalogChannel(executor=executor)
        responses = []

        await executor.start_executor()
        await trio.sleep(1)

        for _ in range(100):
            ts, t, te = await executor.get_echo_clock()
            responses.append((te - ts) / 1e6)

        await executor.ensure_remote_instance(device)
        ts = time.perf_counter_ns()
        for _ in range(100):
            await device.read_state()
        te = time.perf_counter_ns()

        await device.pump_state(100)
        rate_cont = 100 * 1e9 / (time.perf_counter_ns() - te)
        await executor.delete_remote_instance(device)

        await executor.stop_executor(block=True)

    response = sum(responses) / len(responses)
    print(f'Quart-external - {cls.__name__}; '
          f'Round-trip lag: {response:.2f}ms. '
          f'Rate: {100 * 1e9 / (te - ts):.2f}Hz. '
          f'Continuous rate: {rate_cont:.2f}Hz')


async def measure_cls_lag(cls):
    executor = cls()
    device = RandomAnalogChannel(executor=executor)
    requests = []
    responses = []

    await executor.start_executor()
    await trio.sleep(1)

    for _ in range(100):
        ts, t, te = await executor.get_echo_clock()
        requests.append((t - ts) / 1e6)
        responses.append((te - t) / 1e6)

    if not isinstance(executor, AsyncThreadExecutor):
        if hasattr(executor, 'ensure_remote_instance'):
            await executor.ensure_remote_instance(device)

        ts = time.perf_counter_ns()
        for _ in range(100):
            await device.read_state()
        rate = 100 * 1e9 / (time.perf_counter_ns() - ts)

        ts = time.perf_counter_ns()
        await device.pump_state(100)
        rate_cont = 100 * 1e9 / (time.perf_counter_ns() - ts)

        if hasattr(executor, 'ensure_remote_instance'):
            await executor.delete_remote_instance(device)
    else:
        rate_cont = rate = 0

    await executor.stop_executor(block=True)

    request = sum(requests) / len(requests)
    response = sum(responses) / len(responses)
    print(f'{cls.__name__}; Request lag: {request:.2f}ms. '
          f'Response lag: {response:.2f}ms. Rate: {rate:.2f}Hz. '
          f'Continuous rate: {rate_cont:.2f}Hz')


async def measure_no_executor_lag():
    device = RandomAnalogChannel()

    ts = time.perf_counter_ns()
    for _ in range(100):
        await device.read_state()
    rate = 100 * 1e9 / (time.perf_counter_ns() - ts)

    ts = time.perf_counter_ns()
    await device.pump_state(100)
    rate_cont = 100 * 1e9 / (time.perf_counter_ns() - ts)

    print(f'No executor; Rate: {rate:.2f}Hz. '
          f'Continuous rate: {rate_cont:.2f}Hz')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='PyMoa performance tester.')
    parser.add_argument(
        '--host', dest='host', action='store', default="127.0.0.1")
    parser.add_argument(
        '--port', dest='port', action='store', default=5000, type=int)
    args = parser.parse_args()

    for cls in (RestExecutor, WebSocketExecutor):
        trio.run(measure_within_process_quart_lag, cls)
        # only run if quart app is serving externally
        trio.run(measure_outside_process_quart_lag, cls, args.host, args.port)

    for cls in (ThreadExecutor, AsyncThreadExecutor, DummyRemoteExecutor):
        trio.run(measure_cls_lag, cls)

    trio.run(measure_no_executor_lag)

    """
Quart-internal - RestExecutor; Request lag: 10.11ms. Response lag: 1.92ms. \
Rate: 78.54Hz. Continuous rate: 1067.32Hz
Quart-external - RestExecutor; Round-trip lag: 8.68ms. Rate: 95.36Hz. \
Continuous rate: 1495.93Hz
Quart-internal - WebSocketExecutor; Request lag: 0.63ms. \
Response lag: 0.75ms. Rate: 324.92Hz. Continuous rate: 795.35Hz
Quart-external - WebSocketExecutor; Round-trip lag: 2.20ms. \
Rate: 533.46Hz. Continuous rate: 1104.19Hz
ThreadExecutor; Request lag: 0.21ms. Response lag: 0.45ms. \
Rate: 2789.56Hz. Continuous rate: 5395.46Hz
AsyncThreadExecutor; Request lag: 0.65ms. Response lag: 0.51ms. Rate: 0.00Hz. \
Continuous rate: 0.00Hz
DummyRemoteExecutor; Request lag: 0.06ms. Response lag: 0.01ms. \
Rate: 10327.27Hz. Continuous rate: 5739.54Hz
No executor; Rate: 246669.96Hz. Continuous rate: 10018.94Hz

When connecting to an external PI, we got:
Quart-external - RestExecutor; Round-trip lag: 16.56ms. Rate: 59.52Hz. \
Continuous rate: 847.97Hz
Quart-external - WebSocketExecutor; Round-trip lag: 6.14ms. Rate: 153.43Hz. \
Continuous rate: 377.19Hz
    """
