

__all__ = ('StageSimpleDisplay', )


from kivy.uix.gridlayout import GridLayout
from kivy.lang import Builder


simple_display_kv = '''
<StageSimpleDisplay>
    cols: 1
    size_hint_y: None
    height: self.minimum_height
    no_selection: True
    BoxLayout:
        padding: 20, 10
        spacing: 10
        size_hint_y: None
        height: min(name_label.texture_size[1], 50)
        Label:
            id: name_label
            padding: 10, 20
            text: '{}: {:.2f}'.format(root.stage.name, root.stage.elapsed_time)
            text_size: self.width, None
            valign: 'middle'
            halign: 'center'
        GridLayout:
            size_hint_x: None
            width: self.minimum_width
            cols: 2
            ToggleButton:
                size_hint_x: None
                width: self.texture_size[0]
                padding: 10, 0
                text: 'Disable'
                state: 'down' if root.stage.disabled else 'normal'
                on_state: root.stage.disabled = self.state == 'down'
            ToggleButton:
                size_hint_x: None
                width: self.texture_size[0]
                padding: 10, 0
                text: 'Pause'
                state: 'down' if root.stage.paused else 'normal'
                on_state: root.stage.paused = self.state == 'down'
    BoxLayout:
        padding: 25, 10
        spacing: 20
        size_hint_y: None
        height: min(count_label.texture_size[1], 50)
        ProgressBar:
            max: root.stage.repeat
            value: root.stage.count + 1
        Label:
            id: count_label
            text: '{} / {}'.format(root.stage.count + 1, root.stage.repeat)
            size_hint_x: None
            width: self.texture_size[0]
            padding: 10, 10
            canvas:
                Color:
                    rgba: (0.9, 0, .5, .3) if root.stage.finished else \
                    (0, 0.8, 0, 0.4) if root.stage.started else (0, 0, 0, 0)
                Rectangle:
                    pos: self.pos
                    size: self.size
'''
Builder.load_string(simple_display_kv)


class StageSimpleDisplay(GridLayout):
    pass
