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
from chat_downloader.debugging import (
    set_testing_mode,
    set_log_level,
    TestingModes as Modes
)


class TestChatDownloader(unittest.TestCase):
    pass


def generator(site, test):

    def test_template(self):

        site_object = ChatDownloader()
        try:
            params = test['params']
            params.update({
                'max_attempts': 5,
                'interruptible_retry': False,
            })

            expected_result = test.get('expected_result') or {}

            if not params:
                raise Exception('No parameters specified.') # Invalid test

            messages_list = []
            try:
                chat = site_object.get_chat(**params)

                # Ensure the site created matches the test site
                if site is not BaseChatDownloader:
                    self.assertEqual(
                        chat.site.__class__.__name__, site.__name__)

                messages_list = list(chat)

            except Exception as e:
                errors = expected_result.get('error')
                if not isinstance(errors, (list, tuple)):
                    errors = [errors]

                correct_error = any(error is not None and isinstance(e, error) for error in errors)
                if not correct_error:
                    raise e

            messages_condition = expected_result.get('messages_condition')

            if messages_condition:
                if callable(messages_condition):
                    self.assertTrue(messages_condition(messages_list))
                else:
                    raise Exception('Message check is not callable.') # Invalid test

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

    for test_number, test in enumerate(test_cases, start=1):
        test_method = generator(site, test)
        test_method.__name__ = f'test_{site.__name__}_{test_number}'

        setattr(TestChatDownloader, test_method.__name__, test_method)

        del test_method

set_log_level('debug')
set_testing_mode(Modes.EXIT_ON_DEBUG)
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


# pytest -v tests/test_chat_downloader.py::TestChatDownloader::test_YouTubeChatDownloader_1  --log-cli-level=DEBUG -s ttt/
