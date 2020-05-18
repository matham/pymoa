
import trio
import time

from pymoa.executor.remote.app.quart import create_app
from pymoa.executor.remote.rest.client import RestExecutor
from pymoa.executor.threading import ThreadExecutor, AsyncThreadExecutor
from pymoa.executor.remote.dummy import DummyRemoteExecutor
from pymoa.device.analog import RandomAnalogChannel
from pymoa.executor.remote.socket.websocket_client import WebSocketExecutor
from pymoa.executor.remote.socket.multiprocessing_client import \
    MultiprocessSocketExecutor


async def measure_executor(executor, name):
    cls = executor.__class__
    device = RandomAnalogChannel(executor=executor)
    responses = []

    for _ in range(100):
        ts, t, te = await executor.get_echo_clock()
        responses.append((te - ts) / 1e6)

    if hasattr(executor, 'ensure_remote_instance'):
        await executor.ensure_remote_instance(device)

    if not isinstance(executor, AsyncThreadExecutor):
        ts = time.perf_counter_ns()
        for _ in range(100):
            await device.read_state()

        te = time.perf_counter_ns()
        rate = 100 * 1e9 / (te - ts)

        await device.pump_state(100)
        rate_cont = 100 * 1e9 / (time.perf_counter_ns() - te)
    else:
        rate = rate_cont = 0

    if hasattr(executor, 'delete_remote_instance'):
        await executor.delete_remote_instance(device)

    response = sum(responses) / len(responses)
    print(f'{name} - {cls.__name__}; '
          f'Round-trip lag: {response:.2f}ms. '
          f'Rate: {rate:.2f}Hz. '
          f'Continuous rate: {rate_cont:.2f}Hz')


async def measure_within_process_quart_lag(cls, port):
    app = create_app()
    async with trio.open_nursery() as socket_nursery:
        if cls is RestExecutor:
            executor = RestExecutor(uri=f'http://127.0.0.1:{port}')
        else:
            executor = WebSocketExecutor(
                nursery=socket_nursery, server='127.0.0.1', port=port)

        async with trio.open_nursery() as nursery:
            nursery.start_soon(app.run_task, "127.0.0.1", port)
            await trio.sleep(1)

            async with app.app_context():
                await executor.start_executor()

                await measure_executor(executor, 'Quart-internal')

                await executor.stop_executor(block=True)

            nursery.cancel_scope.cancel()


async def measure_outside_process_quart_lag(cls, host='127.0.0.1', port=5000):
    async with trio.open_nursery() as socket_nursery:
        if cls is RestExecutor:
            executor = RestExecutor(uri=f'http://{host}:{port}')
        else:
            executor = WebSocketExecutor(
                nursery=socket_nursery, server=host, port=port)

        await executor.start_executor()
        await trio.sleep(1)

        await measure_executor(executor, 'Quart-external')

        await executor.stop_executor(block=True)


async def measure_multiprocess_lag(host='127.0.0.1', port=5000):
    executor = MultiprocessSocketExecutor(server=host, port=port)

    await executor.start_executor()
    await trio.sleep(1)

    await measure_executor(executor, 'multiprocess')

    await executor.stop_executor(block=True)


async def measure_cls_lag(cls):
    executor = cls()

    await executor.start_executor()
    await trio.sleep(1)

    await measure_executor(executor, 'local')

    await executor.stop_executor(block=True)


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
    parser.add_argument(
        '--port_internal', dest='port_internal', action='store', default=5001,
        type=int)
    args = parser.parse_args()

    for cls in (RestExecutor, WebSocketExecutor):
        trio.run(measure_within_process_quart_lag, cls, args.port_internal)
        # only run if quart app is serving externally
        trio.run(measure_outside_process_quart_lag, cls, args.host, args.port)

    trio.run(measure_multiprocess_lag, args.host, args.port_internal)

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
multiprocess - MultiprocessSocketExecutor; Round-trip lag: 0.48ms. \
Rate: 1132.06Hz. Continuous rate: 3144.60Hz
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
