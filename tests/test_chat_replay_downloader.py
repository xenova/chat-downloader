import unittest

#sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#from chat_replay_downloader import chat_replay_downloader

from chat_replay_downloader.sites import GET_ALL_SITES
from chat_replay_downloader.sites.common import ChatDownloader

from chat_replay_downloader import ChatReplayDownloader

# python tests/test_chat_replay_downloader.py
class TestChatReplayDownloader(unittest.TestCase):

    # @staticmethod
    # def _test_site(site,init_params, program_params):
    #     pass

    def test_all_sites(self):  # test method names begin with 'test'

        downloader = ChatReplayDownloader() # init_params

        #cha
        all_sites = GET_ALL_SITES()

        for site in all_sites:
            tests = list(ChatDownloader.get_tests(site))
            #print(tests)
            for test in tests:

                test['params']['messages'] = []
                params = test['params']
                #print(params)
                expected_result = test.pop('expected_result', None)

                #print(params) #, expected_result
                if(not (params and expected_result)):
                    assert False


                q = downloader.get_chat_messages(params)
                # try:
                #     q = downloader.get_chat_messages(params) # TODO  returns None?
                # except Exception as e:
                #     print(e)
                #     #print('error')
                #     pass




                actual_result = {
                    'message_types': [],
                    'action_types': []
                }
                types_to_check = actual_result.keys()

                for message in test['params']['messages']:
                    message_type = message.get('message_type')
                    if(message_type not in actual_result['message_types']):
                        actual_result['message_types'].append(message_type)

                    action_type = message.get('action_type')
                    if(action_type not in actual_result['action_types']):
                        actual_result['action_types'].append(action_type)

                for check in types_to_check:
                    # print(expected_result.get(check),actual_result.get(check))
                    self.assertCountEqual(expected_result.get(check),actual_result.get(check))

    # def test_ultiply(self):
    #     self.assertEqual((0 * 10), 0)
    #     self.assertEqual((5 * 8), 40)

if __name__ == '__main__':
    unittest.main()


    # downloader = ChatReplayDownloader(init_params)
    # q = downloader.get_chat_messages(options)
