import trio


async def test_write_channel():
    from pymoa.device.digital import RandomDigitalChannel
    device = RandomDigitalChannel(name='rand_device')
    count = 0

    def callback(*args):
        nonlocal count
        count += 1
    device.fbind('on_data_update', callback)

    assert device.name == 'rand_device'
    assert device.state is None

    await device.write_state(True)
    assert device.state
    assert count == 1
    timestamp = device.timestamp
    await trio.sleep(.01)

    await device.write_state(True)
    assert device.state
    assert device.timestamp > timestamp
    timestamp = device.timestamp
    assert count == 2
    await trio.sleep(.01)

    await device.write_state(False)
    assert not device.state
    assert device.timestamp > timestamp
    assert count == 3


async def test_read_channel():
    from pymoa.device.digital import RandomDigitalChannel
    device = RandomDigitalChannel(name='rand_device')
    count = 0

    def callback(*args):
        nonlocal count
        count += 1
    device.fbind('on_data_update', callback)

    assert device.name == 'rand_device'
    assert device.state is None

    await device.read_state()
    assert device.state is not None
    assert count == 1
    timestamp = device.timestamp
    await trio.sleep(.01)

    await device.read_state()
    assert device.timestamp > timestamp
    assert count == 2


async def test_pump_channel(nursery: trio.Nursery):
    from pymoa.device.digital import RandomDigitalChannel
    device = RandomDigitalChannel(name='rand_device')
    count = 0

    def callback(*args):
        nonlocal count
        count += 1
    device.fbind('on_data_update', callback)

    assert device.name == 'rand_device'
    assert device.state is None

    nursery.start_soon(device.pump_state, 10)

    await trio.sleep(.1)

    assert device.state is not None
    assert count >= 1
