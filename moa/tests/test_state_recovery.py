
import unittest


class RecoveryTestCase(unittest.TestCase):

    def setUp(self):
        import os
        from os import path
        self.path = path.join(path.abspath(path.dirname(__file__)), 'temp')
        try:
            os.mkdir(self.path)
        except OSError:
            pass

    def test_recovery(self):
        from moa.app import MoaApp
        from moa.stage.base import MoaStage
        from kivy.lang import Builder

        class RecoveryStage(MoaStage):

            _count = 0

            @property
            def idd(self):
                self.__class__._count += 1
                return str(self.__class__._count)

        Builder.load_string('''
<RecoveryStage>:
    a: a
    b: b
    c: c
    d: d
    name: 'root' + self.idd
    MoaStage:
        id: a
        name: 'child a' + root.idd
    MoaStage:
        id: b
        name: 'child b' + root.idd
        MoaStage:
            id: d
    MoaStage:
        id: c
        name: 'child c' + root.idd
        ''')

        class TestApp(MoaApp):
            def __init__(self, **kw):
                super(TestApp, self).__init__(**kw)
                self.root_stage = RecoveryStage()

        app = TestApp(data_directory=self.path)
        root = app.root_stage
        app.root_stage.d.count = app.root_stage.b.count = 10
        app.root_stage.d.finished = app.root_stage.b.finished = True

        f_named = app.dump_attributes(prefix='test_recovery_')
        f_unnamed = app.dump_attributes(save_unnamed=True)
        clean_stage = RecoveryStage()

        app.root_stage = RecoveryStage()
        app.load_attributes(f_unnamed, verify_name=False)
        self.assertEqual(root.b.count, app.root_stage.b.count)
        self.assertEqual(root.b.finished, app.root_stage.b.finished)
        self.assertEqual(clean_stage.d.count, app.root_stage.d.count)
        self.assertEqual(clean_stage.d.finished, app.root_stage.d.finished)
        self.assertNotEqual(root.d.count, app.root_stage.d.count)
        self.assertNotEqual(root.d.finished, app.root_stage.d.finished)

        app.root_stage = RecoveryStage()
        app.load_attributes(f_named, verify_name=False)
        self.assertEqual(root.b.count, app.root_stage.b.count)
        self.assertEqual(root.b.finished, app.root_stage.b.finished)
        self.assertEqual(clean_stage.d.count, app.root_stage.d.count)
        self.assertEqual(clean_stage.d.finished, app.root_stage.d.finished)
        self.assertNotEqual(root.d.count, app.root_stage.d.count)
        self.assertNotEqual(root.d.finished, app.root_stage.d.finished)

        app.root_stage = RecoveryStage()
        app.load_attributes(f_unnamed, recover_unnamed=True, verify_name=False)
        self.assertEqual(root.b.count, app.root_stage.b.count)
        self.assertEqual(root.b.finished, app.root_stage.b.finished)
        self.assertNotEqual(clean_stage.d.count, app.root_stage.d.count)
        self.assertNotEqual(clean_stage.d.finished, app.root_stage.d.finished)
        self.assertEqual(root.d.count, app.root_stage.d.count)
        self.assertEqual(root.d.finished, app.root_stage.d.finished)

        stage = RecoveryStage()
        app.load_attributes(f_named, stage=stage, recover_unnamed=True,
                          verify_name=False)
        self.assertEqual(root.b.count, stage.b.count)
        self.assertEqual(root.b.finished, stage.b.finished)
        self.assertEqual(clean_stage.d.count, stage.d.count)
        self.assertEqual(clean_stage.d.finished, stage.d.finished)
        self.assertNotEqual(root.d.count, stage.d.count)
        self.assertNotEqual(root.d.finished, stage.d.finished)
