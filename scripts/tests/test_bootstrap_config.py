import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("prism_bootstrap", ROOT / "bootstrap.py")
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class CrawlerConfigTests(unittest.TestCase):
    def test_clean_checkout_creates_empty_configs_and_preserves_user_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for platform in ('tiktok', 'bilibili'):
                relative = Path('prism_backend/douyin_tiktok_api/crawlers') / platform / 'web/config.example.yaml'
                (root / relative).parent.mkdir(parents=True)
                shutil.copyfile(ROOT / relative, root / relative)
            (root / 'env.example').write_text('EXAMPLE=1\n')
            with patch.object(bootstrap, 'REPO_ROOT', root):
                bootstrap.ensure_env()
                config = root / 'prism_backend/douyin_tiktok_api/crawlers/tiktok/app/config.yaml'
                self.assertIn('Cookie: ""', config.read_text())
                config.write_text('user settings')
                (root / '.env').write_text('EXAMPLE=custom\n')
                bootstrap.ensure_env()
                self.assertEqual(config.read_text(), 'user settings')
                self.assertEqual((root / '.env').read_text(), 'EXAMPLE=custom\n')
