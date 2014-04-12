
from kivy.config import Config
Config.set('kivy', 'exit_on_escape', 0)
from moa.bases import MoaApp
from moa.stage.base import MoaStage
from moa.render.treerender import TreeRender


class RootStage(MoaStage):
    pass


class PlaygroundApp(MoaApp):

    root_stage = None
    root_renderer = None

    def build(self):
        renderer = self.root_renderer = TreeRender()
        root = self.root_stage = RootStage(stage_render=renderer)
        renderer.set_root_stage(root)
        return renderer.get_root_widget()

    def on_start(self):
        self.start_root_stage(self.root_stage)

if __name__ == '__main__':
    app = PlaygroundApp()
    app.run()
