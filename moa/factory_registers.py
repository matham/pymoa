from kivy.factory import Factory

r = Factory.register
r('MoaStage', module='moa.stage')
r('Delay', module='moa.stage.delay')
r('GateStage', module='moa.stage.gate')

r('StageRender', module='moa.stage.base')
r('TreeRender', module='moa.render.treerender')
r('TreeRenderExt', module='moa.render.treerender')
r('StageTreeNode', module='moa.render.treerender')
r('StageSimpleDisplay', module='moa.render.stage_simple')
