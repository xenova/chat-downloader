import os
import sys
import unittest
import argparse
import itertools
# Allow direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa

from chat_downloader import run
from chat_downloader.sites import get_all_sites

args = {
    'timeout': 60,
    'max_tests_per_site': 100,  # 100

    # For Twitch:
    'livestream_limit': 10,
    'vod_limit': 5,
    'clip_limit': 5
}
# ,


try:
    new_args = []

    args_index = sys.argv.index('--args')
    sys.argv.pop(args_index)
    new_args = sys.argv.pop(args_index).split()

    # Parse args and use this when creating the test cases
    parser = argparse.ArgumentParser(
        description='Testing suite for chat-downloader. Sites generate appropriate video URLs and tests them with the specified arguments.',
        formatter_class=argparse.RawTextHelpFormatter, usage=argparse.SUPPRESS
    )

    parser.add_argument(
        '--timeout', default=args['timeout'], type=float, help='The maximum time that any single test may run for.')
    parser.add_argument(
        '--max_tests_per_site', default=args['max_tests_per_site'], type=int, help='The maximum number of tests that any site can generate.')




    parser.add_argument(
        '--livestream_limit', default=args['livestream_limit'], type=int, help='The maximum number of livestreams to generate.')
    parser.add_argument(
        '--vod_limit', default=args['vod_limit'], type=int, help='The maximum number of vods to generate.')
    parser.add_argument(
        '--clip_limit', default=args['clip_limit'], type=int, help='The maximum number of clips to generate.')

    args.update(parser.parse_args(new_args).__dict__)

except ValueError:
    pass

class TestURLGenerators(unittest.TestCase):
    """
    Test case generator for all sites. For each site, URLs are generated with the class'
    generate method. The test methods ensure that nothing unexpected happens.
    """
    pass


def generator(site, url):

    def test_template(self):
        params = {
            'url': url,
            'timeout': args['timeout'],
            'exit_on_debug': True,
            'quiet': True,
            'interruptible': True,
        }

        print('\r ➤ ', url)
        run(**params)

    return test_template


print('Arguments:', args)
for site in get_all_sites():
    url_generator = getattr(site, 'generate_urls', None)

    try:
        print('Generating', args['max_tests_per_site'],
              'tests for', site.__name__)
        urls = itertools.islice(url_generator(), args['max_tests_per_site'])
        list_of_urls = list(urls)
        num_tests = len(list_of_urls)
        padding = len(str(num_tests))

        for i, url in enumerate(list_of_urls):
            name = str(i + 1).zfill(padding)

            test_method = generator(site, url)
            test_method.__name__ = 'test_{}_{}_{}'.format(
                site.__name__, name, url)
            setattr(TestURLGenerators, test_method.__name__, test_method)

            del test_method

    except NotImplementedError:
        pass  # No generator, skip

print('Running test cases:')
if __name__ == '__main__':
    unittest.main()

    # python tests/test_generators.py --args "--max_tests_per_site 500 --timeout 120 --livestream_limit 20 --vod_limit 50 --clip_limit 50"

    # pytest -v tests/test_generators.py
    # pytest -v tests/test_generators.py -k YouTubeChatDownloader
    # pytest -v tests/test_generators.py -k TwitchChatDownloader
