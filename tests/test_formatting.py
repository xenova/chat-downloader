import os
import sys
import unittest

# Allow direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa


from chat_downloader import ChatDownloader


class TestFormatting(unittest.TestCase):
    """
    Class used to run unit tests for formatting.
    """

    def test_formatting(self):
        test_url = 'https://www.youtube.com/watch?v=jfKfPfyJRdk'
        chat = ChatDownloader().get_chat(test_url, format='24_hour', max_messages=10)
        for message in chat:
            chat.print_formatted(message)
