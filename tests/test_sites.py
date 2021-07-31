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
                'video_status': 'live'
            },
            {
                'user_id': 'NASAtelevision',
                'video_status': 'all'
            },
            {
                'custom_username': 'overwatchleague',
                'video_status': 'past'
            },
            {
                'channel_id': 'UCS9uQI-jC3DE0L4IpXyvr6w',
                'video_status': 'upcoming'
            }
        ]

        for test in tests:
            videos = downloader.get_user_videos(**test)
            self.assertGreater(
                len(list(itertools.islice(videos, max_videos))), 0)

        downloader.close()
