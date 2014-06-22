

__all__ = ('TreeRender', 'StageTreeNode')

from kivy.uix.treeview import TreeViewNode
from kivy.properties import ObjectProperty
from kivy.lang import Builder
from moa.stage import MoaStage

tree_render_kv = '''
ScrollView:
    tree: tree
    TreeView:
        size_hint_y: None
        id: tree
        height: self.minimum_height
'''


class StageTreeNode(TreeViewNode):

    stage = ObjectProperty(MoaStage(), rebind=True)


class TreeRender(object):

    _treeview = None
    root_widget = None
    _root_stage = None

    def __init__(self, root_stage=None, *args, **kwargs):
        super(TreeRender, self).__init__(*args, **kwargs)

        self.root_widget = Builder.load_string(tree_render_kv)
        self._treeview = self.root_widget.tree
        self._treeview.root.no_selection = True

    def build_tree(self, root_stage=None):
        root_stage = self._root_stage = root_stage or self._root_stage

        tree = self._treeview
        for node in tree.root.nodes:
            tree.remove_node(node)
        if root_stage is None:
            return

        def add_nodes(node, stage, tree):
            children = stage.children
            if len(children) and isinstance(children[0], TreeViewNode):
                if isinstance(children[0], StageTreeNode):
                    children[0].stage = stage
                tree.add_node(children[0], node)
                node = children[0]

            for sub_stage in stage.stages:
                add_nodes(node, sub_stage, tree)

        add_nodes(tree.root, root_stage, tree)
