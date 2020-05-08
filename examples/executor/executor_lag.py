
import trio
import time

from pymoa.executor.remote.rest.quart_app import create_app
from pymoa.executor.remote.rest.client import RestExecutor
from pymoa.executor.threading import ThreadExecutor, AsyncThreadExecutor
from pymoa.executor.remote.dummy import DummyRemoteExecutor
from pymoa.device.analog import RandomAnalogChannel


async def measure_within_process_quart_lag():
    app = create_app()
    executor = RestExecutor(uri='http://127.0.0.1:5001')
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

            await executor.delete_remote_instance(device)
            await executor.stop_executor(block=True)

        nursery.cancel_scope.cancel()

    request = sum(requests) / len(requests)
    response = sum(responses) / len(responses)
    print(f'Quart-internal; Request lag: {request:.2f}ms. '
          f'Response lag: {response:.2f}ms. '
          f'Rate: {100 * 1e9 / (te - ts):.2f}Hz')


async def measure_outside_process_quart_lag():
    executor = RestExecutor(uri='http://127.0.0.1:5000')
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
    await executor.delete_remote_instance(device)

    await executor.stop_executor(block=True)

    response = sum(responses) / len(responses)
    print(f'Quart-external; Round-trip lag: {response:.2f}ms. '
          f'Rate: {100 * 1e9 / (te - ts):.2f}Hz')


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

        if hasattr(executor, 'ensure_remote_instance'):
            await executor.delete_remote_instance(device)
    else:
        rate = 0

    await executor.stop_executor(block=True)

    request = sum(requests) / len(requests)
    response = sum(responses) / len(responses)
    print(f'{cls.__name__}; Request lag: {request:.2f}ms. '
          f'Response lag: {response:.2f}ms. Rate: {rate:.2f}Hz')


async def measure_no_executor_lag():
    device = RandomAnalogChannel()

    ts = time.perf_counter_ns()
    for _ in range(100):
        await device.read_state()
    rate = 100 * 1e9 / (time.perf_counter_ns() - ts)

    print(f'No executor; Rate: {rate:.2f}Hz')


if __name__ == '__main__':
    trio.run(measure_within_process_quart_lag)
    # only run if quart app is serving externally
    trio.run(measure_outside_process_quart_lag)

    for cls in (ThreadExecutor, AsyncThreadExecutor, DummyRemoteExecutor):
        trio.run(measure_cls_lag, cls)

    trio.run(measure_no_executor_lag)

    """
    Typical output is:
    Quart-internal; Request lag: 10.45ms. Response lag: 1.89ms. Rate: 77.12Hz
    Quart-external; Round-trip lag: 8.98ms. Rate: 92.95Hz
    ThreadExecutor; Request lag: 0.10ms. Response lag: 0.23ms. Rate: 2662.90Hz
    AsyncThreadExecutor; Request lag: 0.40ms. Response lag: 0.33ms. \
Rate: 0.00Hz
    DummyRemoteExecutor; Request lag: 0.04ms. Response lag: 0.01ms. \
Rate: 19776.92Hz
    No executor; Rate: 451467.27Hz
    """
