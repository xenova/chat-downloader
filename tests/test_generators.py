import os
import sys
import unittest

# Allow direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa

from chat_downloader import run
from chat_downloader.sites import get_all_sites

class TestURLGenerators(unittest.TestCase):
    """
    Test case generator for all sites. For each site, URLs are generated with the class'
    generate method. The test methods ensure that nothing unexpected happens.
    """
    pass


def generator(site, url):

    def test_template(self):
        run(url=url,
            timeout=10,
            exit_on_debug=True,
            quiet=True,
            interruptible=True
            )

    return test_template


for site in get_all_sites():
    url_generator = getattr(site, 'generate_urls', None)

    try:
        urls = url_generator()
        list_of_urls = list(urls)
        num_tests = len(list_of_urls)
        padding = len(str(num_tests))

        for i, url in enumerate(list_of_urls):
            name = str(i + 1).zfill(padding)

            test_method = generator(site, url)
            test_method.__name__ = 'test_{}_url_{}'.format(site.__name__, name)
            setattr(TestURLGenerators, test_method.__name__, test_method)

        del test_method

    except NotImplementedError:
        pass  # No generator, skip


if __name__ == '__main__':
    unittest.main()
