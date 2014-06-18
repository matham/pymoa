
import unittest


class RecoveryTestCase(unittest.TestCase):

    def test_naming(self):
        from moa.stage.base import MoaStage
        import gc
        stage_a = MoaStage(name='a')
        self.assertEqual(stage_a.name, 'a')
        stage_b = MoaStage()
        self.assertEqual(stage_b.name, '')
        stage_b.name = 'b'
        self.assertEqual(stage_b.name, 'b')
        self.assertRaises(ValueError, MoaStage, name='a')
        self.assertRaises(ValueError, MoaStage, name='b')

        stage_a2 = MoaStage()
        stage_b2 = MoaStage()
        self.assertRaises(ValueError, setattr, stage_a2, 'name', 'a')
        self.assertRaises(ValueError, setattr, stage_b2, 'name', 'b')

        stage_a.name = ''
        self.assertEqual(stage_a.name, '')
        stage_a3 = MoaStage(name='a')
        self.assertEqual(stage_a3.name, 'a')
        stage_a3.name = ''
        self.assertEqual(stage_a3.name, '')

        stage_a4 = MoaStage()
        stage_a4.name = 'a'
        self.assertRaises(ValueError, MoaStage, name='a')
        stage_a4 = None
        gc.collect()
        stage_a5 = MoaStage(name='a')
        self.assertEqual(stage_a5.name, 'a')
