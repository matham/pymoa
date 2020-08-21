from pymoa.stage import MoaStage
from pymoa.stage.delay import Delay, UniformRandomDelay
from pymoa.stage.gate import DigitalGateStage
from pymoa.device.digital import RandomDigitalChannel
from pymoa.data_logger import SimpleTerminalLogger
from kivy_trio.context import kivy_trio_context_manager
import trio


class GroupStage(MoaStage):

    async def do_trial(self):
        pass


class SugarPalletStage(MoaStage):

    motor_device: RandomDigitalChannel = None

    def __init__(self, device, **kwargs):
        super(SugarPalletStage, self).__init__(**kwargs)
        self.motor_device = device

    async def do_trial(self):
        await self.motor_device.write_state(True)
        await trio.sleep(0.2)
        await self.motor_device.write_state(False)


photo_bream_device = RandomDigitalChannel(name='photobeam_device')
motor_device = RandomDigitalChannel(name='motor_device')

root = GroupStage(name='Root stage')
trial = GroupStage(name='Trial', repeat=2)

root.add_stage(Delay(delay=20, name='Habituation'))
root.add_stage(trial)
root.add_stage(Delay(delay=15, name='post delay'))

trial.add_stage(DigitalGateStage(
    device=photo_bream_device, exit_state=True, name='photobeam_stage'))
trial.add_stage(SugarPalletStage(
    device=motor_device, name='sugar pallet stage'))
trial.add_stage(UniformRandomDelay(min=20, max=40, name='ITI'))


logger = SimpleTerminalLogger(separator=',')
for stage in root.iterate_stages():
    logger.add_trigger_logged_names(
        stage, trigger_names=[
            'on_stage_start', 'on_trial_start', 'on_trial_end',
            'on_stage_end'],
        logged_names=['count']
    )


async def run_experiment():
    with kivy_trio_context_manager():
        async with trio.open_nursery() as nursery:
            async def run_root_stage():
                # run the experiment stages, but when done also cancel reading
                # the devices
                await root.run_stage()
                nursery.cancel_scope.cancel()

            # reads the photobeam device continuously
            nursery.start_soon(photo_bream_device.pump_state, 1000)
            # runs the experiment stages
            nursery.start_soon(run_root_stage)

trio.run(run_experiment)
