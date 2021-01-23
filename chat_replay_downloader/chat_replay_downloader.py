"""Main module."""
import datetime
import re
from urllib.parse import urlparse

from .errors import *

from .sites import get_all_sites

from .utils import (
    log
)


class ChatReplayDownloader:

    def __init__(self, init_params=None):
        self._INIT_PARAMS = init_params or {}

    def get_chat(self, params):
        url = params.get('url')  # the only required argument
        if not url:
            raise URLNotProvided('No URL provided.')

        # loop through all websites and
        # get corresponding website parser
        # based on matching url with predefined regex
        correct_site = None
        for site in get_all_sites():
            regex = getattr(site, '_VALID_URL')
            if isinstance(regex, str) and re.search(regex, url):  # regex has been set (not None)
                with site(self._INIT_PARAMS) as correct_site:
                    new_keys = {key: params[key]
                        for key in correct_site._DEFAULT_PARAMS if correct_site._DEFAULT_PARAMS.get(key) != params.get(key)}

                    log('info', 'Site: {}'.format(correct_site))
                    log('debug','Parameters: {}'.format(new_keys))

                    info = correct_site.get_chat(params)
                    setattr(info, 'site', site)
                    return info

        parsed = urlparse(url)

        if parsed.scheme:
            log('debug', str(parsed))
            raise SiteNotSupported('Site not supported: {}'.format(parsed.netloc))
        else:
            params['url'] = 'https://'+params['url'] # try to correct
            chat = self.get_chat(params)
            if chat:
                return chat

            log('debug', parsed)
            raise InvalidURL('Invalid URL: "{}"'.format(url))
