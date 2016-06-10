
import unittest


class RecoveryTestCase(unittest.TestCase):

    path = ''

    def setUp(self):
        import os
        from os import path
        self.path = path.join(path.abspath(path.dirname(__file__)),
                              'mrec_temp')
        if not os.path.exists(self.path):
            os.mkdir(self.path)

    def tearDown(self):
        from shutil import rmtree
        if self.path:
            rmtree(self.path, ignore_errors=True)

    def test_recovery(self):
        from moa.app import MoaApp
        from moa.stage import MoaStage
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
    order: 'parallel'
    knsname: 'root' + self.idd
    restore_properties: ['count', 'finished']
    MoaStage:
        id: a
        knsname: 'child_a' + root.idd
        restore_properties: ['count', 'finished']
    MoaStage:
        id: b
        knsname: 'child_b' + root.idd
        restore_properties: ['count', 'finished']
        MoaStage:
            id: d
            restore_properties: ['count', 'finished']
    MoaStage:
        id: c
        knsname: 'child_c' + root.idd
        restore_properties: ['count', 'finished']
        ''')

        class TestApp(MoaApp):
            def __init__(self, **kw):
                super(TestApp, self).__init__(**kw)
                self.root_stage = RecoveryStage()

        app = TestApp(data_directory=self.path, recovery_directory=self.path)
        root = app.root_stage
        app.root_stage.d.count = app.root_stage.b.count = 10
        app.root_stage.d.finished = app.root_stage.b.finished = True

        f_named = app.dump_recovery(prefix='test_recovery_',
                                    save_unnamed_stages=False)
        f_unnamed = app.dump_recovery(save_unnamed_stages=True)
        clean_stage = RecoveryStage()

        app.root_stage = RecoveryStage()
        app.load_recovery(f_unnamed, verify=False,
                          recover_unnamed_stages=False)
        app.root_stage.step_stage()
        self.assertEqual(root.b.count, app.root_stage.b.count)
        self.assertEqual(root.b.finished, app.root_stage.b.finished)
        self.assertEqual(clean_stage.d.count, app.root_stage.d.count)
        self.assertEqual(clean_stage.d.finished, app.root_stage.d.finished)
        self.assertNotEqual(root.d.count, app.root_stage.d.count)
        self.assertNotEqual(root.d.finished, app.root_stage.d.finished)

        app.root_stage = RecoveryStage()
        app.load_recovery(f_named, verify=False, recover_unnamed_stages=False)
        app.root_stage.step_stage()
        self.assertEqual(root.b.count, app.root_stage.b.count)
        self.assertEqual(root.b.finished, app.root_stage.b.finished)
        self.assertEqual(clean_stage.d.count, app.root_stage.d.count)
        self.assertEqual(clean_stage.d.finished, app.root_stage.d.finished)
        self.assertNotEqual(root.d.count, app.root_stage.d.count)
        self.assertNotEqual(root.d.finished, app.root_stage.d.finished)

        app.root_stage = RecoveryStage()
        app.load_recovery(f_unnamed, recover_unnamed_stages=True, verify=False)
        app.root_stage.step_stage()
        self.assertEqual(root.b.count, app.root_stage.b.count)
        self.assertEqual(root.b.finished, app.root_stage.b.finished)
        self.assertNotEqual(clean_stage.d.count, app.root_stage.d.count)
        self.assertNotEqual(clean_stage.d.finished, app.root_stage.d.finished)
        self.assertEqual(root.d.count, app.root_stage.d.count)
        self.assertEqual(root.d.finished, app.root_stage.d.finished)

        stage = RecoveryStage()
        app.load_recovery(f_named, stage=stage, recover_unnamed_stages=True,
                          verify=False)
        stage.step_stage()
        self.assertEqual(root.b.count, stage.b.count)
        self.assertEqual(root.b.finished, stage.b.finished)
        self.assertEqual(clean_stage.d.count, stage.d.count)
        self.assertEqual(clean_stage.d.finished, stage.d.finished)
        self.assertNotEqual(root.d.count, stage.d.count)
        self.assertNotEqual(root.d.finished, stage.d.finished)
