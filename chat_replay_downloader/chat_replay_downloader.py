"""Main module."""
import datetime
import re

from .errors import *

from .sites import GET_ALL_SITES

from .utils import (
    log
)


class ChatReplayDownloader:
    #"""A simple tool used to retrieve YouTube/Twitch chat from past broadcasts/VODs. No authentication needed!"""

    # _HEADERS = {
    #     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36',
    #     'Accept-Language': 'en-US, en'
    # }

    def __init__(self, init_params={}):
        self._INIT_PARAMS = init_params

    #LIST_OF_MESSAGES = []

    # used for debugging
    #__TYPES_OF_KNOWN_MESSAGES = []
    # for key in __TYPES_OF_MESSAGES:
    #	__TYPES_OF_KNOWN_MESSAGES.extend(__TYPES_OF_MESSAGES[key])


# def get_chat_messages(self, url, list_of_messages = []):

# python -m chat_replay_downloader

    # def close(self):
    #     self.session.close()

    # , start_time=0, end_time=None, message_type='messages', chat_type='live', callback=None
    # TODO add dictionary params ->

    def get_chat_messages(self, params):
        # super().get
        url = params.get('url')  # the only required argument
        if not url:
            # TODO raise error
            return

        if params.get('verbose'):
            params['logging'] = 'errors'

        logging_level = params.get('logging')
        pause_on_debug = params.get('pause_on_debug')

        # self.LIST_OF_MESSAGES = [] # reset list of messages
        # TODO add a reset_messages() method?

        # loop through all websites and
        # get corresponding website parser,
        # based on matching url with predefined regex
        correct_site = None
        for site in GET_ALL_SITES():
            regex = getattr(site, '_VALID_URL')
            # print(regex)
            # print(site, flush=True)
            if isinstance(regex, str) and re.search(regex, url):  # regex has been set (not None)
                with site(self._INIT_PARAMS) as correct_site:

                    new_keys = {key: params[key]
                        for key in correct_site._DEFAULT_PARAMS if correct_site._DEFAULT_PARAMS.get(key) != params.get(key)}

                    log('site', correct_site, logging_level)
                    log(
                        'debug',
                        'Parameters: {}'.format(new_keys),
                        logging_level,
                        matching=('debug', 'errors')
                    )
                    return correct_site.get_chat_messages(params)

        # Raise unsupported site

        # TODO raise invalid url error
        #raise InvalidURL('The url provided ({}) is invalid.'.format(url))
        #raise SiteNotSupported

        # match = re.search(self.__YT_REGEX, url)
        # if(match):
        #     return self.get_youtube_messages(match.group(1), start_time, end_time, message_type, chat_type, callback)

        # match = re.search(self.__TWITCH_REGEX, url)
        # if(match):
        #     return self.get_twitch_messages(match.group(1), start_time, end_time, callback)


# when used as a module
# def get_chat_replay(url, start_time=0, end_time=None, message_type='messages', chat_type='live', callback=None):
#     return ChatReplayDownloader().get_chat_replay(url, start_time, end_time, message_type, chat_type, callback)

# def get_youtube_messages(url, start_time=0, end_time=None, message_type='messages', chat_type='live', callback=None):
#     return ChatReplayDownloader().get_youtube_messages(url, start_time, end_time, message_type, chat_type, callback)

# def get_twitch_messages(url, start_time=0, end_time=None, callback=None):
#     return ChatReplayDownloader().get_twitch_messages(url, start_time, end_time, callback)
