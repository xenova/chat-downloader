import os
import sys
import unittest
import tempfile

# Allow direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa


from chat_downloader.cli import main


class TestCLI(unittest.TestCase):
    """
    Class used to run unit tests for the command line.
    """

    def test_cli(self):
        url = 'https://www.youtube.com/watch?v=jfKfPfyJRdk'
        args = [url, '--timeout', '10']
        main(args)
