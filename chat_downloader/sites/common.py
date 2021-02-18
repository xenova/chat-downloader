
import requests
from http.cookiejar import MozillaCookieJar
import os
from json import JSONDecodeError

from ..errors import (
    InvalidParameter,
    RetriesExceeded,
    CookieError,
    UnexpectedError
)

from ..utils import (
    get_title_of_webpage,
    pause,
    timed_input,
    safe_print
)

from ..debugging import log


class Remapper():
    def __init__(self, new_key=None, remap_function=None, to_unpack=False):
        """[summary]

        :param new_key: [description], defaults to None
        :type new_key: [type], optional
        :param remap_function: [description], defaults to None
        :type remap_function: [type], optional
        :param to_unpack: [description], defaults to False
        :type to_unpack: bool, optional
        :raises ValueError: if unable to perform a remapping
        """

        if new_key is not None and to_unpack:
            # New key is specified, but must unpack. Not allowed
            raise ValueError(
                'If to_unpack is True, new_key may not be specified.')

        self.new_key = new_key

        if isinstance(remap_function, staticmethod):
            remap_function = remap_function.__func__

        if remap_function is None or not (hasattr(remap_function, '__call__')):
            raise ValueError('remap_function must be callable or None.')

        self.remap_function = remap_function
        self.to_unpack = to_unpack


    @staticmethod
    def remap(info, remapping_dict, remap_key, remap_input, keep_unknown_keys=False, replace_char_with_underscores=None):
        """A function used to remap items from one dictionary to another

        :param info: Output dictionary
        :type info: dict
        :param remapping_dict: Dictionary of remappings
        :type remapping_dict: dict
        :param remap_key: The key of the remapping
        :type remap_key: str
        :param remap_input: The input sent to the remapping function
        :type remap_input: object
        :param keep_unknown_keys: If no remapping is found, keep the data
            with its original key and value. Defaults to False
        :type keep_unknown_keys: bool, optional
        :param replace_char_with_underscores: If no remapping is found,
            replace a character in the key with underscores. Defaults to None
        :type replace_char_with_underscores: str, optional
        :raises ValueError: if attempting to unpack an item that is not a dictionary,
            or if an unknown remapping is specified
        """

        remap = remapping_dict.get(remap_key)

        if remap:  # A matching 'remapping' has been found, apply this remapping
            if isinstance(remap, Remapper):
                new_key = remap.new_key  # or remap_key

                # Perform transformation
                if remap.remap_function:  # Has a remap function
                    new_value = remap.remap_function(remap_input)
                else:  # No remap function specified, apply identity transformation
                    new_value = remap_input

                # Assign values to info
                if not remap.to_unpack:
                    info[new_key] = new_value
                elif isinstance(new_value, dict):
                    info.update(new_value)
                else:
                    raise ValueError(
                        'Unable to unpack item which is not a dictionary.')

            elif isinstance(remap, str):
                # If it is just a string, simply assign the new value to this key
                info[remap] = remap_input
            else:
                raise ValueError('Unknown remapping specified.')

        elif keep_unknown_keys:
            if replace_char_with_underscores:
                remap_key = remap_key.replace(
                    replace_char_with_underscores, '_')
            info[remap_key] = remap_input

    @staticmethod
    def remap_dict(input_dictionary, remapping_dict, keep_unknown_keys=False, replace_char_with_underscores=None):
        """Given an input dictionary and a remapping dictionary, return the remapped dictionary

        :param input_dictionary: Input dictionary
        :type input_dictionary: dict
        :param remapping_dict: Dictionary of Remapper objects
        :type remapping_dict: dict
        :param keep_unknown_keys: If no remapping is found, keep the data
            with its original key and value. Defaults to False
        :type keep_unknown_keys: bool, optional
        :param replace_char_with_underscores: If no remapping is found,
            replace a character in the key with underscores. Defaults to None
        :type replace_char_with_underscores: str, optional
        :return: Remapped dictionary
        :rtype: dict
        """

        info = {}
        for key in input_dictionary:
            Remapper.remap(
                info, remapping_dict, key, input_dictionary[key],
                keep_unknown_keys=keep_unknown_keys,
                replace_char_with_underscores=replace_char_with_underscores
            )
        return info

class SiteDefault:
    # Used for site-default parameters
    def __init__(self, name):
        self.name = name


class Chat():
    """Class used to manage all chat data for a single stream or video.

    Classes that extend `BaseChatDownloader` contain the `get_chat` method,
    which returns a `Chat` object. These objects are iterable, where the
    next value is yielded from the object's `chat` generator method.
    """

    def __init__(self, chat, callback=None, title=None, duration=None, is_live=None, start_time=None, **kwargs):
        """Create a Chat object

        :param chat: Generator method for retrieving chat messages
        :type chat: generator
        :param callback: Function to call on every message, defaults to None
        :type callback: function, optional
        :param title: Stream or video title, defaults to None
        :type title: str, optional
        :param duration: Duration of the stream or video, defaults to None
        :type duration: float, optional
        :param is_live: True if the stream is live, defaults to None
        :type is_live: bool, optional
        :param start_time: Start time of the stream (or upload date of video)
            in UNIX microseconds, defaults to None
        :type start_time: float, optional
        """

        self.chat = chat

        self.callback = callback
        self.title = title
        self.duration = duration
        self.is_live = is_live
        self.start_time = start_time

        # TODO
        # author/user/uploader/creator

    def __iter__(self):
        """Allows the object to be iterable

        :return: The generator method which retrieves chat messages
        :rtype: generator
        """
        return self

    def __next__(self):
        item = next(self.chat)
        if self.callback:
            self.callback(item)
        return item

    def print_formatted(self, item):
        formatted = self.format(item)
        safe_print(formatted)

    def format(self, item):
        """[summary]

        :param item: [description]
        :type item: [type]
        :raises NotImplementedError: [description]
        """
        raise NotImplementedError


class BaseChatDownloader:
    """Base class for chat downloaders. Each supported site should have its
    own chat downloader. Subclasses should redefine the `get_chat()` method
    and `_VALID_URL` regexp. Optionally, subclasses should also redefine
    `_NAME`, `_SITE_DEFAULT_PARAMS` and `_TESTS` fields.

    """

    _NAME = None
    _VALID_URL = None

    _SITE_DEFAULT_PARAMS = {
        # MAY NOT specify message_types. must always be empty
        'message_groups': ['messages'],
        'format': 'default',
    }

    # For general tests (non-site specific)
    _TESTS = [
        {
            'name': 'Get a certain number of messages from a livestream.',
            'params': {
                'url': 'https://www.youtube.com/watch?v=5qap5aO4i9A',
                'max_messages': 10,
                'timeout': 60,  # As a fallback
            },

            'expected_result': {
                'messages_condition': lambda messages: len(messages) <= 10,
            }
        }
    ]

    @staticmethod
    def must_add_item(item, message_groups_dict, messages_groups_to_add, messages_types_to_add):

        # Force mutual exclusion
        if messages_types_to_add:
            # messages_types is set
            messages_groups_to_add = []

        if 'all' in messages_groups_to_add or 'all' in messages_types_to_add:  # user wants everything
            return True

        valid_message_types = []
        for message_group in messages_groups_to_add or []:
            valid_message_types += message_groups_dict.get(message_group, [])

        for message_type in messages_types_to_add or []:
            valid_message_types.append(message_type)

        return item.get('message_type') in valid_message_types

    @staticmethod
    def debug_log(params, *items):
        """Method which simplifies the logging of debugging messages

        :param params: Dictionary of parameters sent to the `get_chat` method
        :type params: dict
        :raises UnexpectedError: if something unexpected occurs, but is only
            used when debugging
        """
        log(
            'debug',
            items,
            params.get('pause_on_debug')
        )
        if params.get('exit_on_debug'):
            raise UnexpectedError(items)

    def __init__(self,
                 **kwargs
                 ):
        """Initialise a session with various parameters

        :raises CookieError: if unable to read or parse the cookie file
        """

        # Start a new session
        self.session = requests.Session()

        headers = kwargs.get('headers')
        if headers is None:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36',
                'Accept-Language': 'en-US, en'
            }
        self.session.headers = headers

        # Set proxies if present
        proxy = kwargs.get('proxy')
        if proxy is not None:
            if proxy == '':
                proxies = {}
            else:
                proxies = {'http': proxy, 'https': proxy}

            self.session.proxies.update(proxies)

        # Set cookies if present
        cookies = kwargs.get('cookies')
        cj = MozillaCookieJar(cookies)

        if cookies:  # is not None
            # Only attempt to load if the cookie file exists.
            if os.path.exists(cookies):
                cj.load(ignore_discard=True, ignore_expires=True)
            else:
                raise CookieError(
                    'The file "{}" could not be found.'.format(cookies))
        self.session.cookies = cj

    def get_session_headers(self, key):
        return self.session.headers.get(key)

    def update_session_headers(self, new_headers):
        self.session.headers.update(new_headers)

    def clear_cookies(self):
        self.session.cookies.clear()

    def get_cookies_dict(self):
        return requests.utils.dict_from_cookiejar(self.session.cookies)

    def get_cookie_value(self, name, default=None):
        return self.get_cookies_dict().get(name, default)

    def close(self):
        self.session.close()
        log('debug', 'Session closed.')

    def _session_post(self, url, **kwargs):
        """Make a request using the current session."""
        return self.session.post(url, **kwargs)

    def _session_get(self, url, **kwargs):
        """Make a request using the current session."""
        return self.session.get(url, **kwargs)

    def _session_get_json(self, url, **kwargs):
        """Make a request using the current session and get json data."""
        return self._session_get(url, **kwargs).json()

    def get_site_value(self, v):
        if isinstance(v, SiteDefault):
            return self._SITE_DEFAULT_PARAMS.get(
                v.name, BaseChatDownloader._SITE_DEFAULT_PARAMS.get(v.name))
        else:
            return v

    def get_chat(self, **kwargs):
        """[summary]

        :raises NotImplementedError: if not implemented and called from a subclass
        """
        raise NotImplementedError

    @staticmethod
    def generate_urls(**kwargs):
        """[summary]

        :raises NotImplementedError: if not implemented and called from a subclass
        """
        raise NotImplementedError

    @staticmethod
    def create_image(url, width=None, height=None, image_id=None):
        if url.startswith('//'):
            url = 'https:' + url
        image = {
            'url': url,
        }
        if width:
            image['width'] = width
        if height:
            image['height'] = height

        # TODO remove id?
        if width and height and not image_id:
            image['id'] = '{}x{}'.format(width, height)
        elif image_id:
            image['id'] = image_id

        return image

    @staticmethod
    def move_to_dict(info, dict_name, replace_key=None, create_when_empty=False, *info_keys):
        """
        Move all items with keys that contain some text to a separate dictionary.

        These keys are modifed by removing some text.
        """
        if replace_key is None:
            replace_key = dict_name + '_'

        new_dict = {}

        for key in (info_keys or info or {}).copy():
            if replace_key in key:
                info_item = info.pop(key, None)
                new_key = key.replace(replace_key, '')

                # set it if it contains info
                if info_item not in (None, [], {}):
                    new_dict[new_key] = info_item

        if dict_name in info:
            info[dict_name].update(new_dict)
        elif create_when_empty or new_dict != {}:  # dict_name not in info
            info[dict_name] = new_dict

        return new_dict

    @staticmethod
    def retry(attempt_number, max_attempts, error, retry_timeout=None, text=None):
        """[summary]

        :param attempt_number: [description]
        :type attempt_number: [type]
        :param max_attempts: [description]
        :type max_attempts: [type]
        :param error: [description]
        :type error: [type]
        :param retry_timeout: [description], defaults to None
        :type retry_timeout: [type], optional
        :param text: [description], defaults to None
        :type text: [type], optional
        :raises RetriesExceeded: if the maximum number of retries has been exceeded
        """
        if attempt_number >= max_attempts:
            raise RetriesExceeded(
                'Maximum number of retries has been reached ({}).'.format(max_attempts))

        if text is None:
            text = []
        elif not isinstance(text, (tuple, list)):
            text = [text]

        if retry_timeout is None:  # use exponential backoff
            if attempt_number > 1:
                time_to_sleep = 2**(attempt_number - 2)
            else:
                time_to_sleep = 0

        elif isinstance(retry_timeout, (int, float)):  # valid timeout value
            time_to_sleep = retry_timeout
        else:
            time_to_sleep = -1  # wait for user input

        must_sleep = time_to_sleep >= 0
        if must_sleep:
            sleep_text = '(sleep for {}s or press Enter)'.format(time_to_sleep)
        else:
            sleep_text = ''

        retry_text = 'Retry #{} {}. {} ({})'.format(
            attempt_number, sleep_text, error, error.__class__.__name__)

        log(
            'warning',
            text + [retry_text]
        )

        if isinstance(error, JSONDecodeError):
            log(
                'debug',
                error.__dict__
            )
            page_title = get_title_of_webpage(error.doc)
            if page_title:
                log('debug', 'Title: {}'.format(page_title))

        if must_sleep:
            # time.sleep(time_to_sleep)
            timed_input(time_to_sleep)
        else:
            pause()

    @staticmethod
    def check_for_invalid_types(messages_types_to_add, allowed_message_types):
        """[summary]

        :param messages_types_to_add: [description]
        :type messages_types_to_add: [type]
        :param allowed_message_types: [description]
        :type allowed_message_types: [type]
        :raises InvalidParameter: if invalid types are specified
        """
        invalid_types = set(messages_types_to_add) - set(allowed_message_types)
        if invalid_types:
            raise InvalidParameter(
                'Invalid types specified: {}'.format(invalid_types))

    @staticmethod
    def get_mapped_keys(remapping):
        mapped_keys = set()
        for key in remapping:
            value = remapping[key]

            if isinstance(value, Remapper):
                value = value.new_key
            mapped_keys.add(value)

        return mapped_keys
