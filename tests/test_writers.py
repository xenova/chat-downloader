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

        test_urls = [
            'https://www.youtube.com/watch?v=jfKfPfyJRdk',
            'https://www.youtube.com/channel/UCSJ4gkVC6NrvII8umztf0Ow'
        ]

        downloader = ChatDownloader()

        with tempfile.TemporaryDirectory() as tmp:
            for index, test_url in enumerate(test_urls):
                # Test types of writers
                for extension in ContinuousWriter._SUPPORTED_WRITERS:
                    path = os.path.join(tmp, f'test_{index}.{extension}')

                    chat = list(downloader.get_chat(
                        test_url, max_messages=10, output=path))

                    # ensure output is non-empty
                    size = os.stat(path).st_size
                    self.assertFalse(size == 0)

                    # Test appending
                    chat = list(downloader.get_chat(
                        test_url, max_messages=10, output=path, overwrite=False))

                    self.assertGreater(os.stat(path).st_size, size)

                    # Test file name formatting
                    formatting_path = os.path.join(
                        tmp, f'{{id}}_{{title}}.{extension}')
                    chat = downloader.get_chat(
                        test_url, max_messages=10, output=formatting_path)
                    list(chat)  # Iterate over items

                    self.assertTrue(os.path.exists(
                        chat._output_writer.file_name))
