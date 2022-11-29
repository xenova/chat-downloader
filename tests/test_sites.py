import os
import sys
import unittest

# Allow direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa


from chat_downloader.sites import YouTubeChatDownloader
import itertools


class TestSites(unittest.TestCase):
    """
    Class used to run unit tests for writers.
    """

    def test_youtube(self):

        max_videos = 50

        downloader = YouTubeChatDownloader()
        tests = [
            {
                'channel_id': 'UCSJ4gkVC6NrvII8umztf0Ow',
                'video_type': 'live'
            }
        ]

        for test in tests:
            videos = downloader.get_user_videos(**test)
            self.assertGreater(
                len(list(itertools.islice(videos, max_videos))), 0)

        downloader.close()
