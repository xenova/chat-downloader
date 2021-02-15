import os
import sys
import unittest
from requests.exceptions import ProxyError


# Allow direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa


from chat_downloader import ChatDownloader


class TestInitParams(unittest.TestCase):
    """
    Class used to run unit tests for initialisation parameters.
    """

    def _get_one_message(self, expected_error=None, **init_params):
        session = ChatDownloader(**init_params)

        try:
            url = 'https://www.youtube.com/watch?v=5qap5aO4i9A'
            chat = list(session.get_chat(url, max_messages=1))

            self.assertEqual(len(chat), 1)

        except Exception as e:
            self.assertTrue(
                expected_error is not None and isinstance(e, expected_error))
        finally:
            session.close()

    def test_proxy(self):
        # TODO
        # Find secure way to do unit testing with proxies
        # Add param for random proxy selector?
        # TODO do not allow proxies with cookies for security reasons

        # https://github.com/clarketm/proxy-list
        # http://pubproxy.com/
        # http://pubproxy.com/api/proxy?limit=1&format=json&type=socks5

        # Testing already done for http, https and socks5 proxies:
        # All working as of this commit

        # These tests should pass
        proxies_to_test = ('', None)

        for proxy in proxies_to_test:
            self._get_one_message(proxy=proxy)

        # These tests should fail
        self._get_one_message(proxy='fake_proxy', expected_error=ProxyError)

    def test_headers(self):

        test_user_agents = {
            'windows': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36',
            'mac': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36',
            'linux': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36'
        }

        for user_agent in test_user_agents.values():
            test_headers = {
                'User-Agent': user_agent,
                'Accept-Language': 'en-US, en'
            }
            self._get_one_message(headers=test_headers)

    def test_cookies(self):
        # TODO safe way to test cookies
        pass
