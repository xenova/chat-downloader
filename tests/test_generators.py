import os
import sys
import unittest
import argparse
import itertools
# Allow direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa

from chat_downloader import (run, ChatDownloader)
from chat_downloader.sites import get_all_sites
from chat_downloader.cli import splitter
from chat_downloader.debugging import (
    set_testing_mode,
    set_log_level,
    TestingModes as Modes
)

args = {
    # Tests
    'max_tests_per_site': 50,
    'sites': ['all'],

    # Program params
    'timeout': 10,
    'max_attempts': 5,
    'interruptible_retry': False,

    # For Twitch and Facebook:
    'livestream_limit': 10,
    'vod_limit': 20,
    'clip_limit': 20
}

if __name__ == '__main__':  # Do not parse args if using pytest

    # Parse args and use this when creating the test cases
    parser = argparse.ArgumentParser(
        description='Testing suite for chat-downloader. Sites generate appropriate video URLs and tests them with the specified arguments.',
        formatter_class=argparse.RawTextHelpFormatter, usage=argparse.SUPPRESS
    )

    parser.add_argument(
        '--timeout', default=60, type=float, help='The maximum time that any single test may run for.')
    parser.add_argument(
        '--sites', '-k', default=['all'], type=splitter, help='The sites to generates tests for.')
    parser.add_argument(
        '--max_tests_per_site', default=100, type=int, help='The maximum number of tests that any site can generate.')

    # For Twitch:
    parser.add_argument(
        '--livestream_limit', default=30, type=int, help='The maximum number of livestreams to generate.')
    parser.add_argument(
        '--vod_limit', default=35, type=int, help='The maximum number of vods to generate.')
    parser.add_argument(
        '--clip_limit', default=35, type=int, help='The maximum number of clips to generate.')

    args.update(parser.parse_args().__dict__)


class TestURLGenerators(unittest.TestCase):
    """
    Test case generator for all sites. For each site, URLs are generated with the class'
    generate method. The test methods ensure that nothing unexpected happens.
    """
    pass


def generator(site, url):

    def test_template(self):
        print('\r ➤ ', url)
        run(propagate_interrupt=True, url=url, **args)

    return test_template


downloader = ChatDownloader()


# Small optimisation to generate tests
try:
    args['sites'] = sys.argv[sys.argv.index('-k') + 1].split()

except (ValueError, IndexError) as e:
    pass


args['sites'] = [s.lower() for s in args['sites']]
all_sites = 'all' in args['sites']

print('Arguments:', args)

for site in get_all_sites():
    try:
        if not all_sites and site.__name__.lower() not in args['sites']:
            continue

        print('Generating', args['max_tests_per_site'],
              'tests for', site.__name__)
        urls = itertools.islice(downloader.create_session(
            site).generate_urls(**args), args['max_tests_per_site'])
        list_of_urls = list(urls)
        num_tests = len(list_of_urls)
        padding = len(str(num_tests))

        for i, url in enumerate(list_of_urls):
            name = str(i + 1).zfill(padding)

            test_method = generator(site, url)
            test_method.__name__ = f'test_{site.__name__}_{name}_{url}'
            setattr(TestURLGenerators, test_method.__name__, test_method)

            del test_method

    except NotImplementedError:
        pass  # No generator, skip

set_log_level('debug')
set_testing_mode(Modes.EXIT_ON_DEBUG)
if __name__ == '__main__':
    print('Running test cases:')
    sys.argv = sys.argv[:1]
    unittest.main()

    # YouTubeChatDownloader TwitchChatDownloader FacebookChatDownloader RedditChatDownloader
    # python tests/test_generators.py --max_tests_per_site 500 --timeout 120 --livestream_limit 20 --vod_limit 50 --clip_limit 50

    # pytest -n 4 -v tests/test_generators.py -k "YouTubeChatDownloader or TwitchChatDownloader"
    # pytest -n 4 -v tests/test_generators.py
    # pytest -n 4 -v tests/test_generators.py -k YouTubeChatDownloader
    # pytest -n 4 -v tests/test_generators.py -k FacebookChatDownloader
    # pytest -n 4 -v tests/test_generators.py -k TwitchChatDownloader
    # pytest -n 4 -v tests/test_generators.py -k RedditChatDownloader

    # pytest -v tests/test_generators.py -k "YouTubeChatDownloader or TwitchChatDownloader"
    # pytest -v tests/test_generators.py
    # pytest -v tests/test_generators.py -k YouTubeChatDownloader
    # pytest -v tests/test_generators.py -k FacebookChatDownloader
    # pytest -v tests/test_generators.py -k TwitchChatDownloader
    # pytest -v tests/test_generators.py -k RedditChatDownloader
