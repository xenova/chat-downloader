import unittest

# Allow direct execution
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chat_downloader.sites import get_all_sites
from chat_downloader import ChatDownloader

# python tests/test_chat_downloader.py
class TestChatDownloader(unittest.TestCase):

    # def __init__(self, k):
    #     print(k)


    def perform_test(self, site_object, site, test):

        # TODO check that siteobject is instance of site
        params = test['params']

        if not params.get('logging'): # if it is not set, make it 'none'
            pass
            # params['logging'] = 'none'


        expected_result = test.pop('expected_result', None)

        if not params:#( and expected_result):
            assert False # Invalid test

        messages_list = []
        try:
            chat = site_object.get_chat(**params)
            # print(chat)

            messages_list = list(chat)
            # print(messages_list)

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
        types_to_check = [key for key in actual_result if key in expected_result]

        if types_to_check:
            for message in messages_list:
                # print(message.get('message'))

                message_type = message.get('message_type')
                if message_type not in actual_result['message_types']:
                    actual_result['message_types'].append(message_type)

                action_type = message.get('action_type')
                if action_type not in actual_result['action_types']:
                    actual_result['action_types'].append(action_type)


            # for check in types_to_check:
            #     print(expected_result.get(check),actual_result.get(check))

            for check in types_to_check:
                self.assertCountEqual(expected_result.get(check),actual_result.get(check))



    def test_all_sites(self):
        site_object = ChatDownloader()

        all_sites = get_all_sites(True)
        # print(all_sites)
        try:
            line = '='*70
            for site in all_sites:
                print(line)
                print('Running tests for site "{}":'.format(site.__name__))
                print()

                tests = site.get_tests(site)

                test_number = 1
                for test in tests:
                    print('Running test #{}: {}'.format(test_number,test.get('name')))
                    self.perform_test(site_object, site, test)

                    test_number+=1
                print(line)

                print()

        finally:
            site_object.close()

    def test_site(self):
        print('test_site')
    # def test_ultiply(self):
    #     self.assertEqual((0 * 10), 0)
    #     self.assertEqual((5 * 8), 40)

if __name__ == '__main__':
    unittest.main()


    # downloader = ChatReplayDownloader(init_params)
    # q = downloader.get_chat_messages(options)
