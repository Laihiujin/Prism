import json
from pathlib import Path
import unittest

from compile_product_rules import SceneError, compile_scene

SHEET = json.loads((Path(__file__).resolve().parent.parent / 'references' / 'product-logic.example.json').read_text(encoding='utf-8'))


class CompileProductRulesTests(unittest.TestCase):
    def test_single_unit_scene_hides_the_other_unit(self):
        result = compile_scene(SHEET, ['exterior_unit'])
        self.assertIn('no interior unit', result['negative'])
        self.assertTrue(any('camera module at the top faces outward' in line for line in result['prompt']))
        self.assertFalse(any('inside face of the door, home interior' in line for line in result['prompt']))
        self.assertTrue(any(item.startswith('[c1]') for item in result['checklist']))

    def test_two_units_in_one_literal_view_are_refused(self):
        with self.assertRaises(SceneError):
            compile_scene(SHEET, ['exterior_unit', 'interior_unit'])

    def test_liberty_allows_both_units(self):
        result = compile_scene(SHEET, ['exterior_unit', 'interior_unit'], 'split')
        self.assertTrue(any('split-screen' in line for line in result['prompt']))
        self.assertNotIn('no interior unit', result['negative'])

    def test_provisional_sheet_is_flagged(self):
        result = compile_scene(SHEET, ['interior_unit'])
        self.assertTrue(any(item.startswith('[provisional]') for item in result['checklist']))

    def test_unknown_unit_is_refused(self):
        with self.assertRaises(SceneError):
            compile_scene(SHEET, ['mortise'])


if __name__ == '__main__':
    unittest.main()
