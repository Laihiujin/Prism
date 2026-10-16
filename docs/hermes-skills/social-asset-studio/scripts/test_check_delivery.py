import base64
import copy
from pathlib import Path
import tempfile
import unittest

from check_delivery import check, sha256


class DeliveryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9WQAAAAASUVORK5CYII=')
        for name in ('source.png', 'out.png'):
            (self.root / name).write_bytes(png)
        (self.root / 'logic.md').write_text('constraints', encoding='utf-8')
        self.manifest = {
            'expected_count': 1,
            'product_logic_sheets': [{'product_id': 'p', 'path': 'logic.md'}],
            'assets': [{'id': 'p', 'role': 'product_original', 'path': 'source.png', 'sha256': sha256(self.root / 'source.png')}],
            'covers': [{'id': 'one', 'platform': 'douyin', 'version': 'A', 'ratio': '1:1', 'concept_key': 'one',
                        'path': 'out.png', 'required_product_ids': ['p'],
                        'attempts': [{'tool': 'host', 'provider_record': 'call-1', 'original_asset_ids': ['p']}],
                        'product_logic_review': 'pass', 'visual_review': 'pass', 'approved_by_user': True, 'approved_sha256': sha256(self.root / 'out.png')}],
        }

    def test_local_evidence_can_pass(self):
        self.assertEqual(check(self.manifest, self.root, True), [])

    def test_each_edit_requires_original_not_only_first_attempt(self):
        self.manifest['covers'][0]['attempts'].append({'tool': 'host', 'provider_record': 'edit-2', 'original_asset_ids': []})
        self.assertTrue(any('attempt 1 missing original' in e for e in check(self.manifest, self.root)))

    def test_source_changed_since_review_is_rejected(self):
        (self.root / 'source.png').write_bytes(b'changed')
        self.assertTrue(any('original hash mismatch' in e for e in check(self.manifest, self.root)))

    def test_ratio_mismatch_and_stale_user_approval_are_rejected(self):
        self.manifest['covers'][0]['ratio'] = '3:4'
        self.manifest['covers'][0]['approved_sha256'] = 'old-candidate'
        errors = check(self.manifest, self.root, True)
        self.assertTrue(any('aspect ratio mismatch' in e for e in errors))
        self.assertTrue(any('user approval' in e for e in errors))

    def test_product_cover_requires_logic_sheet_and_review(self):
        self.manifest['product_logic_sheets'] = []
        self.manifest['covers'][0]['product_logic_review'] = 'fail'
        errors = check(self.manifest, self.root)
        self.assertTrue(any('no product logic sheet' in e for e in errors))
        self.assertTrue(any('product logic review not passed' in e for e in errors))

    def test_reused_cross_platform_concept_is_flagged(self):
        other = copy.deepcopy(self.manifest['covers'][0])
        other.update(id='two', platform='bilibili')
        self.manifest['covers'].append(other)
        self.manifest['expected_count'] = 2
        self.assertTrue(any('reused concept' in e for e in check(self.manifest, self.root)))


if __name__ == '__main__':
    unittest.main()
