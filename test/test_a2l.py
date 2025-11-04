import sys
import unittest


from a2lparser.a2l_parser import A2LParser

class TestA2LParser(unittest.TestCase):

    def setUp(self):
        self.model = A2LParser().parse_file("test\demo.a2l")
        return super().setUp()

    def test_parse_text(self):
        self.assertEqual(len(self.model.measurements), 2)
        self.assertEqual(self.model.measurements[0].ecu_address, 0x4000D944)
        self.assertEqual(self.model.measurements[0].name, 'Testvar1')
        self.assertEqual(self.model.measurements[1].ecu_address, 0x4000D90C)
        self.assertEqual(self.model.measurements[1].name, 'Testvar12')
        self.assertEqual(len(self.model.characteristics), 3)
        self.assertEqual(self.model.characteristics[0].address, 0xb050C084)
        self.assertEqual(self.model.characteristics[0].name, 'TestCalib1')
        self.assertEqual(self.model.characteristics[1].address, 0xb050C098)
        self.assertEqual(self.model.characteristics[1].name, 'TestCalib2')
        self.assertEqual(self.model.characteristics[2].address, 0xb050C0AC)
        self.assertEqual(self.model.characteristics[2].name, 'TestCalib3')
        self.assertEqual(len(self.model.axis_pts), 2)