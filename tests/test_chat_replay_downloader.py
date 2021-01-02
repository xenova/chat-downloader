# Allow direct execution
import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chat_replay_downloader.sites import GET_ALL_SITES
from chat_replay_downloader.sites.common import ChatDownloader

from chat_replay_downloader import ChatReplayDownloader

# python tests/test_chat_replay_downloader.py
class TestChatReplayDownloader(unittest.TestCase):

    def perform_test(self, site_object, test):
        test['params']['messages'] = []
        params = test['params']

        if not params.get('logging'): # if it is not set, make it 'none'
            params['logging'] = 'none'


        expected_result = test.pop('expected_result', None)

        if not (params and expected_result):
            assert False

        try:
            messages = site_object.get_chat_messages(params)
        except Exception as e:
            error = expected_result.get('error')
            self.assertTrue(error is not None and isinstance(e, error))
        finally:
            site_object.close()

        messages_condition = expected_result.get('messages_condition')

        if messages_condition and callable(messages_condition):
            self.assertTrue(messages_condition(params.get('messages')))


        actual_result = {
            'message_types': [],
            'action_types': []
        }
        types_to_check = [key for key in actual_result if key in expected_result]

        if types_to_check:
            for message in test['params']['messages']:
                #print(message)

                message_type = message.get('message_type')
                if message_type not in actual_result['message_types']:
                    actual_result['message_types'].append(message_type)

                action_type = message.get('action_type')
                if action_type not in actual_result['action_types']:
                    actual_result['action_types'].append(action_type)


            for check in types_to_check:
                #print(expected_result.get(check),actual_result.get(check))
                self.assertCountEqual(expected_result.get(check),actual_result.get(check))



    def test_all_sites(self):

        all_sites = GET_ALL_SITES()

        for site in all_sites:
            site_object = site()
            print('Running tests for site "{}":'.format(site_object))

            tests = ChatDownloader.get_tests(site)

            test_number = 1
            for test in tests:
                print('\tTest #{}: {}'.format(test_number,test.get('name')))
                self.perform_test(site_object, test)

                test_number+=1
            print()

    # def test_ultiply(self):
    #     self.assertEqual((0 * 10), 0)
    #     self.assertEqual((5 * 8), 40)

if __name__ == '__main__':
    unittest.main()


    # downloader = ChatReplayDownloader(init_params)
    # q = downloader.get_chat_messages(options)
