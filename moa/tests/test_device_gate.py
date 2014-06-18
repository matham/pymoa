
import unittest


class RecoveryTestCase(unittest.TestCase):

    def test_naming(self):
        from moa.device.gate import DigitalPort
        names = {'food_hopper': 0, 'wire': 1, 'button': 2}
        port = DigitalPort(mapping=names)
        for key in names.keys():
            self.assert_(hasattr(port, key))

        self.assertRaises(Exception, DigitalPort, mapping={'9wire': 10})
        self.assertRaises(Exception, DigitalPort, mapping={'wire port': 10})
        self.assertRaises(Exception, DigitalPort, mapping={'mapping': 10})
        self.assertRaises(Exception, DigitalPort, mapping={'name': 10})
