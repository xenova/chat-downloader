
import requests
from http.cookiejar import MozillaCookieJar, LoadError
import os
from ..errors import (
    CookieError,
    ParsingError
    )

from ..utils import (
    get_title_of_webpage
    )


from json import JSONDecodeError


class ChatDownloader: #(object):
    """
    Subclasses of this one should re-define the get_chat_messages()
    method and define a _VALID_URL regexp.
    """


    _DEFAULT_INIT_PARAMS = {
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36',
            'Accept-Language': 'en-US, en'
        },

        'cookies': None # cookies file (optional)
    }
    _INIT_PARAMS = _DEFAULT_INIT_PARAMS


    _DEFAULT_PARAMS = {
        'url': None, # should be overridden
        'messages': [], # list of messages to append to
        'start_time': None, # get from beginning (even before stream starts)
        'end_time':None, # get until end
        'callback':None, # do something for every message

    }
    #_PARAMS = _DEFAULT_PARAMS
#_DEFAULT_PARAMS.extend({})

    def __init__(self, updated_init_params = {}):
        self._INIT_PARAMS.update(updated_init_params)


        # = {**self._PARAMS, **updated_init_params}


        """Initialise a new session for making requests."""

        # cookies=None
        self.session = requests.Session()
        self.session.headers = self._INIT_PARAMS.get('headers')
        #self._HEADERS # TODO put this in init_params

        cookies = self._INIT_PARAMS.get('cookies')
        cj = MozillaCookieJar(cookies)

        if cookies: #  is not None
            # Only attempt to load if the cookie file exists.
            if os.path.exists(cookies):
                cj.load(ignore_discard=True, ignore_expires=True)
            else:
                raise CookieError(
                    "The file '{}' could not be found.".format(cookies))
        self.session.cookies = cj

    def _session_get(self, url):
        """Make a request using the current session."""
        return self.session.get(url)

    def _session_get_json(self, url):
        """Make a request using the current session and get json data."""
        s = self._session_get(url)

        try:
            return s.json()
        except JSONDecodeError:
            print(s.text)
            webpage_title = get_title_of_webpage(s.text)
            raise ParsingError(webpage_title)

            #return

    _VALID_URL = None
    _CALLBACK = None

    #_LIST_OF_MESSAGES = []
    def get_chat_messages(self, params = {}):
    #def get_chat_messages(self, url, list_of_messages = []):
        """Get chat. Redefine in subclasses."""
        temp = params.copy()
        params.update(self._DEFAULT_PARAMS)
        params.update(temp)
        #self._PARAMS.update()
        #params.update(self._PARAMS)


