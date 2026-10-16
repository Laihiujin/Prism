import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]


class CleanupCollectionTests(unittest.TestCase):
    def load_module(self):
        spec = importlib.util.spec_from_file_location("manual_cleanup", ROOT / "prism_backend/tests/test_clear_video_data.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_import_does_not_load_database_or_delete_files(self):
        with patch('shutil.rmtree') as remove:
            module = self.load_module()
            self.assertFalse(module.__test__)
            self.assertFalse(any(name.startswith('test_') for name in vars(module)))
            remove.assert_not_called()

    def test_cli_requires_explicit_confirmation(self):
        module = self.load_module()
        with patch.object(module, 'clear_video_data') as clear:
            with self.assertRaises(SystemExit) as error:
                module.main([])
            self.assertEqual(error.exception.code, 2)
            clear.assert_not_called()

    def test_confirmed_cli_preserves_backup_default(self):
        module = self.load_module()
        with patch.object(module, 'clear_video_data', Mock(return_value={'status': 'success'})) as clear:
            self.assertEqual(module.main(['--confirm']), 0)
            clear.assert_called_once_with(backup=True)
