
import unittest


class RecoveryTestCase(unittest.TestCase):

    def test_naming(self):
        from moa.device.gate import DigitalPort
        names = {'food_hopper': 0, 'wire': 1, 'button': 2}
        port = DigitalPort(attr_map=names)
        for key in names.keys():
            self.assert_(hasattr(port, key))

        self.assertRaises(Exception, DigitalPort, attr_map={'9wire': 10})
        self.assertRaises(Exception, DigitalPort, attr_map={'wire port': 10})
        self.assertRaises(Exception, DigitalPort, attr_map={'attr_map': 10})
        self.assertRaises(Exception, DigitalPort, attr_map={'name': 10})
