import unittest


class IntegerArithmeticTestCase(unittest.TestCase):
    def testAdd(self, site):  # test method names begin with 'test'
        self.assertEqual((1 + 2), 3)
        self.assertEqual(0 + 1, 1)
    def testMultiply(self):
        self.assertEqual((0 * 10), 0)
        self.assertEqual((5 * 8), 40)

if __name__ == '__main__':
    unittest.main()


    downloader = ChatReplayDownloader(init_params)
    q = downloader.get_chat_messages(options)
