import os
import sys
import unittest
import tempfile

# Allow direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa


from chat_downloader import ChatDownloader
from chat_downloader.output.continuous_write import ContinuousWriter


class TestWriters(unittest.TestCase):
    """
    Class used to run unit tests for writers.
    """

    def test_writers(self):

        test_url = 'https://www.youtube.com/watch?v=5qap5aO4i9A'

        downloader = ChatDownloader()

        with tempfile.TemporaryDirectory() as tmp:

            # Test types of writers
            for extension in ContinuousWriter._SUPPORTED_WRITERS:
                path = os.path.join(tmp, f'test.{extension}')

                chat = list(downloader.get_chat(
                    test_url, max_messages=10, output=path))

                # ensure output is non-empty
                size_1 = os.stat(path).st_size
                self.assertFalse(size_1 == 0)

                # Test appending
                chat = list(downloader.get_chat(
                    test_url, max_messages=10, output=path, overwrite=False))

                self.assertGreater(os.stat(path).st_size, size_1)

                # Test file name formatting
                formatting_path = os.path.join(tmp, f'{{id}}.{extension}')
                chat = list(downloader.get_chat(
                    test_url, max_messages=10, output=formatting_path))

                self.assertTrue(os.path.exists(formatting_path))
