from kivy.factory import Factory

r = Factory.register
r('MoaStage', module='moa.stage')
r('Delay', module='moa.stage.delay')
r('GateStage', module='moa.stage.gate')

r('StageTreeNode', module='moa.render.treerender')
r('StageSimpleDisplay', module='moa.render.stage_simple')
