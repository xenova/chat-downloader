import json
import os
import sys
import tempfile
import unittest

# Allow direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa

from chat_downloader.errors import FormatError, FormatFileNotFound
from chat_downloader.formatting.format import ItemFormatter


class TestFormatFileErrors(unittest.TestCase):
    """Unit tests for format-file edge cases (offline)."""

    def test_missing_format_file_raises_format_file_not_found(self):
        with self.assertRaises(FormatFileNotFound):
            ItemFormatter(path=os.path.join(tempfile.mkdtemp(), 'no-such-file.json'))

    def test_malformed_format_file_raises_format_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_path = os.path.join(tmp_dir, 'bad.json')
            with open(bad_path, 'w', encoding='utf-8') as f:
                f.write('{not valid json')
            with self.assertRaises(FormatError):
                ItemFormatter(path=bad_path)

    def test_valid_format_file_loads(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            good_path = os.path.join(tmp_dir, 'good.json')
            with open(good_path, 'w', encoding='utf-8') as f:
                json.dump({'default': {'template': '{message}', 'keys': {}}}, f)
            formatter = ItemFormatter(path=good_path)
            self.assertIn('default', formatter.format_file)


if __name__ == '__main__':
    unittest.main()
