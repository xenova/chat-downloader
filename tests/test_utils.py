import os
import sys
import unittest

# Allow direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa


from chat_downloader.utils.core import (
    safe_print,
    get_title_of_webpage
)
from chat_downloader.utils.timed_utils import timed_input


class TestUtils(unittest.TestCase):
    """
    Class used to run unit tests for writers.
    """

    def test_printing(self):
        # https://docs.python.org/3/library/functions.html#chr
        for i in range(0, 0x10FFFF):  # max is 0x10FFFF
            safe_print(chr(i))

    def test_get_title(self):
        self.assertEqual(get_title_of_webpage(
            '<title>test title</title>'), 'test title')
        self.assertEqual(get_title_of_webpage(
            'a <title>title</title> b'), 'title')

    def test_timed_input(self):
        if os.name == 'nt':  # only test on windows
            self.assertEqual(timed_input(5, 'Enter:'), None)
