

__all__ = ('TreeRender', 'TreeRenderExt', 'StageTreeNode')

from moa.stage.base import StageRender
from kivy.uix.treeview import TreeViewNode
from kivy.properties import ObjectProperty
from kivy.clock import Clock
from kivy.lang import Builder

tree_render_kv = '''
ScrollView:
    tree: tree
    TreeView:
        size_hint_y: None
        id: tree
        height: self.minimum_height
'''


class StageTreeNode(TreeViewNode):

    stage = ObjectProperty(None)

    def __init__(self, stage=None, **kwargs):
        self.stage = stage
        super(StageTreeNode, self).__init__(**kwargs)


class TreeRender(StageRender):

    _stages = None
    _treeview = None
    _root_widget = None
    _root_stage = None
    _refresh_trigger = None

    def __init__(self, root_stage=None, *args, **kwargs):
        super(TreeRender, self).__init__(*args, **kwargs)

        self._stages = {}
        self._root_widget = Builder.load_string(tree_render_kv)
        self._treeview = self._root_widget.tree
        self._root_stage = root_stage
        self._treeview.root.no_selection = True
        self._refresh_trigger = Clock.create_trigger(self._refresh)

    def add_render(self, stage, widget, **kwargs):
        if widget is not None and not isinstance(widget, TreeViewNode):
            raise ValueError('{} only accepts TreeViewNode instances for '
                'render instances, not {}'.format(self.__class__.__name__,
                                                  widget))
        stages = self._stages
        if stage not in stages or stages[stage] is None:
            stages[stage] = widget
        else:
            raise KeyError('{} has previously been added to the renderer of '
                           'stage {}'.format(stages[stage], stage))
        self._refresh_trigger()

    def remove_render(self, stage, widget, **kwargs):
        stages = self._stages
        if stage in stages and stages[stage] is widget:
                stages[stage] = None
        self._refresh_trigger()

    def set_root_stage(self, root_stage):
        if self._root_stage is not None and root_stage is not None:
            raise ValueError('Root stage, {}, has already been set. Cannot '
                'set root stage with {}'.format(self._root_stage, root_stage))
        self._root_stage = root_stage
        self._refresh_trigger()

    def get_root_widget(self):
        return self._root_widget

    def _refresh(self, *largs):
        root_stage = self._root_stage
        tree = self._treeview
        stages = self._stages

        for node in tree.root.nodes:
            tree.remove_node(node)
        if root_stage is None:
            return

        def add_nodes(node, stage, stages, tree):
            if stage in stages and stages[stage] is not None:
                tree.add_node(stages[stage], node)
                node = stages[stage]
            for sub_stage in stage.stages:
                add_nodes(node, sub_stage, stages, tree)

        add_nodes(tree.root, root_stage, stages, tree)


class TreeRenderExt(TreeRender):
    pass
