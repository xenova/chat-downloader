"""Main module."""

import re
import itertools

from urllib.parse import urlparse

from .sites.common import SiteDefault
from .sites import get_all_sites

from .errors import (
    URLNotProvided,
    SiteNotSupported,
    InvalidURL
)
from .formatting.format import ItemFormatter
from .utils import log


class ChatDownloader():

    def __init__(self,
                 headers=None,
                 cookies=None,
                 ):
        """
        Initialise a new session for making requests.

        :param headers: Test headers
        :param cookies: Path of cookies file

        """
        self.init_params = locals()
        self.init_params.pop('self')

        # Track a list of sessions
        self.sessions = []

    def get_chat(self, url=None,
                 start_time=None,
                 end_time=None,
                 max_attempts=15,  # ~ 2^15s ~ 9 hours
                 retry_timeout=None,
                 timeout=None,
                 max_messages=None,

                 logging='info',
                 pause_on_debug=False,

                 # If True, program will not sleep when a timeout instruction is given
                 # force_no_timeout=False,
                 # :param force_no_timeout: Force no timeout between subsequent requests
                 #  force_encoding=None, # use default

                 inactivity_timeout=None,

                 message_groups=SiteDefault('message_groups'),
                 message_types=None,  # SiteDefault('message_types'),


                 # Formatting
                 format=SiteDefault('format'),  # Use default
                 format_file=None,

                 # YouTube
                 chat_type='live',

                 # Twitch
                 message_receive_timeout=0.1,
                 buffer_size=4096
                 ):
        """
        Short description

        Long description spanning multiple lines
        - First line
        - Second line
        - Third line

        :param url: The URL of the livestream, video, clip or past broadcast
        :param start_time: Start time in seconds or hh:mm:ss, default is None (as early as possible)
        :param end_time: End time in seconds or hh:mm:ss, default is None (until the end)

        :param message_types: List of messages types to include
        :param message_groups: List of messages groups (a predefined, site-specific collection of message types) to include



        :param max_attempts: Maximum number of attempts to retrieve chat messages
        :param retry_timeout: Number of seconds to wait before retrying. Setting this to a negative number will wait for user input.
        Default is None (use exponential backoff, i.e. immediate, 1s, 2s, 4s, 8s, ...)

        :param max_messages: Maximum number of messages to retrieve, default is None (unlimited)
        :param inactivity_timeout: Stop getting messages after not receiving anything for a certain duration (in seconds)
        :param timeout: Stop retrieving chat after a certain duration (in seconds)

        :param format: Specify how messages should be formatted for printing, default uses site default
        :param format_file: Specify the format file to choose formats from

        :param pause_on_debug: Pause on certain debug messages
        :param logging: Level of logging to display


        :param chat_type: Specify chat type, default is live

        :param message_receive_timeout: Time before requesting for new messages
        :param buffer_size: Specify a buffer size for retrieving messages
        """

        if not url:
            raise URLNotProvided('No URL provided.')

        original_params = locals()
        original_params.pop('self')

        # loop through all websites and
        # get corresponding website parser
        # based on matching url with predefined regex
        for site in get_all_sites():
            regex = getattr(site, '_VALID_URL')
            if isinstance(regex, str) and re.search(regex, url):  # regex has been set (not None)
                correct_site = site(**self.init_params)

                self.sessions.append(correct_site)

                # Parse site-defaults
                params = {}
                for k, v in original_params.items():
                    params[k] = correct_site.get_site_value(v)

                log('info', 'Site: {}'.format(correct_site))
                log('debug', 'Parameters: {}'.format(params))
                info = correct_site.get_chat(**params)
                if isinstance(max_messages, int):
                    info.chat = itertools.islice(info.chat, max_messages)
                setattr(info, 'site', correct_site)

                formatter = ItemFormatter(params['format_file'])
                setattr(info, 'format', lambda x: formatter.format(
                    x, format_name=params['format']))

                return info

        parsed = urlparse(url)

        if parsed.scheme:
            log('debug', str(parsed))
            raise SiteNotSupported(
                'Site not supported: {}'.format(parsed.netloc))
        else:
            original_params['url'] = 'https://' + url  # try to correct
            chat = self.get_chat(**original_params)
            if chat:
                return chat

            log('debug', parsed)
            raise InvalidURL('Invalid URL: "{}"'.format(url))

    def close(self):
        for session in self.sessions:
            session.close()

        self.sessions = []
