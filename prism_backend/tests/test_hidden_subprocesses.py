import subprocess
import sys
import unittest
from unittest.mock import patch

from utils.subprocesses import hidden_process_kwargs


class HiddenSubprocessTests(unittest.TestCase):
    def test_other_platforms_do_not_get_windows_flags(self):
        with patch('utils.subprocesses.sys.platform', 'darwin'):
            self.assertEqual(hidden_process_kwargs(), {})

    @unittest.skipUnless(sys.platform == 'win32', 'Windows console behavior')
    def test_background_python_has_no_console(self):
        result = subprocess.run(
            [sys.executable, '-c', 'import ctypes; print(bool(ctypes.windll.kernel32.GetConsoleWindow()))'],
            capture_output=True, text=True, check=True, **hidden_process_kwargs(),
        )
        self.assertEqual(result.stdout.strip(), 'False')


if __name__ == '__main__':
    unittest.main()
