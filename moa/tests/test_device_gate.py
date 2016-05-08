
import unittest


class RecoveryTestCase(unittest.TestCase):

    def test_naming(self):
        from moa.device.digital import DigitalPort
        from kivy.properties import NumericProperty

        class MyDigitalPort(DigitalPort):

            food_hopper = NumericProperty(0)
            wire = NumericProperty(0)
            button = NumericProperty(0)

        MyDigitalPort(attr_map={'food_hopper': 0, 'wire': 1, 'button': 2})

        self.assertRaises(Exception, DigitalPort, attr_map={'9wire': 10})
        self.assertRaises(Exception, DigitalPort, attr_map={'wire port': 10})
