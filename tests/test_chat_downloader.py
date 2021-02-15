import os
import sys
import unittest

# Allow direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa


from chat_downloader import ChatDownloader
from chat_downloader.sites import (
    get_all_sites,
    BaseChatDownloader
)


class TestChatDownloader(unittest.TestCase):
    pass


def generator(site, test):

    def test_template(self):
        site_object = ChatDownloader()
        try:
            params = test['params']

            if not params.get('logging'):  # if it is not set, make it 'none'
                params['logging'] = 'none'

            expected_result = test.get('expected_result') or {}

            if not params:
                self.assertFalse('No parameters specified.')  # Invalid test

            messages_list = []
            try:
                chat = site_object.get_chat(**params)

                # Ensure the site created matches the test site
                if site is not BaseChatDownloader:
                    self.assertEqual(
                        chat.site.__class__.__name__, site.__name__)

                messages_list = list(chat)

            except Exception as e:
                error = expected_result.get('error')
                self.assertTrue(error is not None and isinstance(e, error))

            messages_condition = expected_result.get('messages_condition')

            if messages_condition:
                if callable(messages_condition):
                    self.assertTrue(messages_condition(messages_list))
                else:
                    self.assertFalse('Message check is not callable.')

            actual_result = {
                'message_types': [],
                'action_types': []
            }
            types_to_check = [
                key for key in actual_result if key in expected_result]

            if types_to_check:
                for message in messages_list:
                    message_type = message.get('message_type')
                    if message_type not in actual_result['message_types']:
                        actual_result['message_types'].append(message_type)

                    action_type = message.get('action_type')
                    if action_type not in actual_result['action_types']:
                        actual_result['action_types'].append(action_type)

                for check in types_to_check:
                    self.assertCountEqual(expected_result.get(
                        check), actual_result.get(check))

        finally:
            site_object.close()

    return test_template


for site in get_all_sites(True):
    test_cases = getattr(site, '_TESTS', [])

    for test_number, test in enumerate(test_cases):
        test_method = generator(site, test)
        test_method.__name__ = 'test_{}_{}'.format(
            site.__name__, test_number + 1)

        setattr(TestChatDownloader, test_method.__name__, test_method)

        del test_method

if __name__ == '__main__':
    # Test all sites:
    # python tests/test_chat_downloader.py
    # or
    # pytest -v tests/test_chat_downloader.py

    # Test specific case:
    # python tests/test_chat_downloader.py TestChatDownloader.test_YouTubeChatDownloader_1
    # or
    # pytest -v tests/test_chat_downloader.py::TestChatDownloader::test_YouTubeChatDownloader_1
    unittest.main()


# print('asdasd')
