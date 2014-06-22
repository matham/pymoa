
from kivy.config import Config
Config.set('kivy', 'exit_on_escape', 0)
from kivy.lang import Builder
from moa.app import MoaApp
from moa.stage import MoaStage
from moa.render.treerender import TreeRender

kv = '''
BoxLayout:
    button: button
    Splitter:
        sizable_from: 'left'
        GridLayout:
            cols: 1
            ToggleButton:
                id: button
'''


class RootStage(MoaStage):
    pass


class PlaygroundApp(MoaApp):

    root_stage = None
    root_renderer = None

    def build(self):
        root = Builder.load_string(kv)

        renderer = self.root_renderer = TreeRender()
        root_stage = self.root_stage = RootStage()
        renderer.build_tree(root_stage)

        root.add_widget(renderer.root_widget, len(root.children))
        return root

    def on_start(self):
        self.root_stage.step_stage()

if __name__ == '__main__':
    app = PlaygroundApp()
    app.run()
