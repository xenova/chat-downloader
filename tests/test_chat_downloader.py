# Allow direct execution
import unittest
from chat_downloader.sites import (
    get_all_sites,
    BaseChatDownloader
)
from chat_downloader import ChatDownloader
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestChatDownloader(unittest.TestCase):
    pass


line = '=' * 70


def generator(site, test_name):

    test_cases = getattr(site, '_TESTS', [])

    def test_template(self):
        print()
        print(line)
        print('Testing site "{}":'.format(site.__name__))
        print()

        site_object = ChatDownloader()
        try:
            for test_number, test in enumerate(test_cases):
                print('Running test #{}: {}'.format(
                    test_number + 1, test.get('name')))

                params = test['params']

                if not params.get('logging'):  # if it is not set, make it 'none'
                    params['logging'] = 'none'

                expected_result = test.pop('expected_result', None)

                if not params:
                    self.assertFalse()  # Invalid test

                messages_list = []
                try:
                    chat = site_object.get_chat(**params)

                    if site is not BaseChatDownloader:
                        self.assertEqual(
                            chat.site.__class__.__name__, site.__name__)

                    messages_list = list(chat)

                except Exception as e:
                    error = expected_result.get('error')
                    self.assertTrue(error is not None and isinstance(e, error))

                messages_condition = expected_result.get('messages_condition')

                if messages_condition and callable(messages_condition):
                    self.assertTrue(messages_condition(messages_list))

                actual_result = {
                    'message_types': [],
                    'action_types': []
                }
                types_to_check = [
                    key for key in actual_result if key in expected_result]

                if types_to_check:
                    for message in messages_list:
                        # print(message.get('message'))

                        message_type = message.get('message_type')
                        if message_type not in actual_result['message_types']:
                            actual_result['message_types'].append(message_type)

                        action_type = message.get('action_type')
                        if action_type not in actual_result['action_types']:
                            actual_result['action_types'].append(action_type)

                    # Used for debugging
                    # for check in types_to_check:
                    #     print(expected_result.get(check),actual_result.get(check))

                    for check in types_to_check:
                        self.assertCountEqual(expected_result.get(
                            check), actual_result.get(check))

        finally:
            site_object.close()
            print()
            print('Finished running tests.')
            print(line)
            print()

    return test_template


all_sites = get_all_sites(True)
for site in all_sites:
    test_name = 'test_' + site.__name__

    test_method = generator(site, test_name)
    test_method.__name__ = str(test_name)

    setattr(TestChatDownloader, test_method.__name__, test_method)

    del test_method


if __name__ == '__main__':
    # Test all sites:
    # python tests/test_chat_downloader.py

    # Test specific site:
    # python tests/test_chat_downloader.py TestChatDownloader.test_YouTubeChatDownloader

    unittest.main()
