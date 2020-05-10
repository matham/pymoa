import trio
from pymoa.device.digital import RandomDigitalChannel
from pymoa.executor.remote.rest.client import RestExecutor


async def test_run_in_quart_executor(
        quart_app, quart_executor: RestExecutor,
        quart_device: RandomDigitalChannel):
    count = 0

    def callback(*args):
        nonlocal count
        count += 1
    quart_device.fbind('on_data_update', callback)

    assert quart_device.name == 'rand_device'
    assert quart_device.state is None

    data = {}
    exec_data = {}

    async def read_exec_gen(task_status=trio.TASK_STATUS_IGNORED):
        nonlocal exec_data
        async for exec_data in quart_executor.get_execute_from_remote(
                quart_device, task_status):
            break

    async def read_data_gen(task_status=trio.TASK_STATUS_IGNORED):
        nonlocal data
        async for data in quart_executor.get_data_from_remote(
                quart_device, task_status):
            break

    async with trio.open_nursery() as nursery:
        await nursery.start(read_data_gen)
        await nursery.start(read_exec_gen)
        nursery.start_soon(quart_device.read_state)

    assert quart_device.state is not None
    assert count == 1
    timestamp = quart_device.timestamp

    assert exec_data
    ex_state, ex_timestamp = exec_data['return_value']

    assert quart_device.timestamp == ex_timestamp
    assert quart_device.state == ex_state

    assert data
    logged_items = data['logged_items']
    assert logged_items['timestamp'] == ex_timestamp
    assert logged_items['state'] == ex_state

    remote_device = quart_app.server_executor.registry.hashed_instances[
        quart_device.hash_val]
    assert remote_device.timestamp == ex_timestamp
    assert remote_device.state == ex_state
    await trio.sleep(.01)

    await quart_device.read_state()
    assert quart_device.timestamp > timestamp
    assert count == 2


async def test_echo_clock(quart_executor: RestExecutor):
    a, b, c = await quart_executor.get_echo_clock()
    assert b >= a
    assert c >= b
