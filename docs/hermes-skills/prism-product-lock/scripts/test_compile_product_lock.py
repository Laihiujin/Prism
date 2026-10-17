import copy
import json
import unittest
from pathlib import Path

import compile_product_lock as lock

REFS = Path(__file__).resolve().parent.parent / 'references'
PLAN = REFS / 'shot-plan.example.json'


def shot(result, shot_id):
    return next(s for s in result['shots'] if s['id'] == shot_id)


class ProductLockTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.card, self.logic = lock.resolve(PLAN)

    def test_originals_come_first_on_product_shots(self):
        result = lock.compile_plan(self.plan, self.card, self.logic)
        refs = shot(result, 'SH-05')['references']
        self.assertEqual(['product_original', 'product_original'], [r['role'] for r in refs[:2]])
        self.assertTrue(shot(result, 'SH-05')['prompt'][0].startswith('Product memory:'))

    def test_swaps_keep_the_product_block(self):
        result = lock.compile_matrix(self.plan, self.card, self.logic,
                                     {'home': ['SCENE-APARTMENT'], 'lead': ['CHAR-LADY']})
        self.assertTrue(result['product_block_stable'])
        self.assertEqual([], result['variants'][0]['blocked'])

    def test_both_panels_in_one_view_are_blocked(self):
        plan = copy.deepcopy(self.plan)
        plan['shots'][4]['visible_units'] = ['exterior_unit', 'interior_unit']
        result = lock.compile_plan(plan, self.card, self.logic)
        self.assertIn('SH-05', result['blocked'])

    def test_generated_image_cannot_be_product_authority(self):
        card = copy.deepcopy(self.card)
        card['originals'][0]['provenance'] = 'generated'
        with self.assertRaises(lock.LockError):
            lock.compile_plan(self.plan, card, self.logic)

    def test_examples_match_their_schemas(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest('jsonschema not installed')
        for example, schema in (('product-lock.example.json', 'product-lock.schema.json'),
                                ('shot-plan.example.json', 'product-shot-plan.schema.json')):
            validator = Draft202012Validator(json.loads((REFS / schema).read_text(encoding='utf-8')))
            data = json.loads((REFS / example).read_text(encoding='utf-8'))
            self.assertEqual([], [e.message for e in validator.iter_errors(data)], example)


if __name__ == '__main__':
    unittest.main()
