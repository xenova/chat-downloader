import os
import sys
import unittest

# Allow direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa


from chat_downloader import ChatDownloader
from chat_downloader.sites import YouTubeChatDownloader
import itertools


class TestSites(unittest.TestCase):
    """
    Class used to run unit tests for writers.
    """

    def test_youtube(self):

        max_videos = 50

        downloader = ChatDownloader()
        youtube = downloader.create_session(YouTubeChatDownloader)
        tests = [
            {
                'prefix': 'channel/',
                'id': 'UCSJ4gkVC6NrvII8umztf0Ow',
                'type': 'channel_id',
                'video_type': 'live'
            },
            # TODO: Find channel with 24/7 live stream
            # {
            #     'prefix': 'user/',
            #     'id': '...',
            #     'type': 'user_id',
            #     'video_type': 'live'
            # },
            {
                'prefix': 'c/',
                'id': 'LofiGirl',
                'type': 'custom_username',
                'video_type': 'live'
            },
            {
                'prefix': '',
                'id': 'LofiGirl',
                'type': 'custom_username',
                'video_type': 'live'
            },
            {
                'prefix': '@',
                'id': 'LofiGirl',
                'type': 'handle',
                'video_type': 'live'
            },
        ]

        num_test_messages = 10
        timeout=10
        for test in tests:
            data = {
                test['type']: test['id'],
                'video_type': test['video_type']
            }
            videos = youtube.get_user_videos(**data)
            self.assertGreater(
                len(list(itertools.islice(videos, max_videos))), 0)

            url = f"https://www.youtube.com/{test['prefix']}{test['id']}"

            chat = list(downloader.get_chat(
                url,
                max_messages=num_test_messages,
                timeout=timeout
            ))
            self.assertEqual(len(chat), num_test_messages)


        downloader.close()
