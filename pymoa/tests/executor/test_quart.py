import trio
from async_generator import aclosing
import pytest
from pymoa.device.digital import RandomDigitalChannel
from pymoa.executor.remote.rest.client import RestExecutor


@pytest.mark.parametrize("protocol", ['rest', 'socket'])
async def test_run_in_quart_rest_executor(
        quart_app, quart_rest_executor: RestExecutor,
        quart_rest_device: RandomDigitalChannel, quart_socket_executor,
        quart_socket_device, protocol):
    if protocol == 'rest':
        executor = quart_rest_executor
        device = quart_rest_device
    else:
        executor = quart_socket_executor
        device = quart_socket_device

    count = 0

    def callback(*args):
        nonlocal count
        count += 1
    device.fbind('on_data_update', callback)

    assert device.name == f'rand_device_{protocol}'
    assert device.state is None

    data = {}
    exec_data = {}

    async def read_exec_gen(task_status=trio.TASK_STATUS_IGNORED):
        nonlocal exec_data
        async with executor.get_execute_from_remote(
                device, task_status) as aiter:
            async for exec_data in aiter:
                break

    async def read_data_gen(task_status=trio.TASK_STATUS_IGNORED):
        nonlocal data
        async with executor.get_data_from_remote(device, task_status) as aiter:
            async for data in aiter:
                break

    async with trio.open_nursery() as nursery:
        await nursery.start(read_data_gen)
        await nursery.start(read_exec_gen)
        nursery.start_soon(device.read_state)

    assert device.state is not None
    assert count == 1
    timestamp = device.timestamp

    assert exec_data
    ex_state, ex_timestamp = exec_data['return_value']

    assert device.timestamp == ex_timestamp
    assert device.state == ex_state

    assert data
    logged_items = data['logged_items']
    assert logged_items['timestamp'] == ex_timestamp
    assert logged_items['state'] == ex_state

    remote_device = quart_app.rest_executor.registry.hashed_instances[
        device.hash_val]
    assert remote_device.timestamp == ex_timestamp
    assert remote_device.state == ex_state
    await trio.sleep(.01)

    await device.read_state()
    assert device.timestamp > timestamp
    assert count == 2


async def test_echo_clock(quart_rest_executor: RestExecutor):
    a, b, c = await quart_rest_executor.get_echo_clock()
    assert b >= a
    assert c >= b
