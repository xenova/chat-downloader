
import requests
from http.cookiejar import MozillaCookieJar, LoadError
import os
import time


from ..errors import (
    CookieError,
    ParsingError,
    CallbackFunction,
    RetriesExceeded,
    InvalidParameter,
    UnexpectedHTML
)

from ..utils import (
    get_title_of_webpage,
    update_dict_without_overwrite,
    log,
    remove_prefixes
)


from json import JSONDecodeError

class Chat():
    def __init__(self, chat, **kwargs):
        self.chat = chat

        self.title = kwargs.get('title')
        self.duration = kwargs.get('duration')
        self.is_live = kwargs.get('is_live')


        # TODO
        # author/user/uploader/creator


    def __iter__(self):
        for item in self.chat:
            yield item




class ChatDownloader:
    """
    Subclasses of this should re-define the get_chat()
    method and define a _VALID_URL regexp.

    Each chat item is a dictionary and must contain the following fields:

    timestamp:          UNIX time (in microseconds) of when the message was sent.
    message:            Actual content/text of the chat item.
    message_id:         Identifier for the chat item.
    message_type:       Message type of the item.
    author:             A dictionary containing information about the user who
                        sent the message.

                        Mandatory fields:
                        * name      The name of the author.
                        * id        Idenfifier for the author.

                        Optional fields:
                        * display_name  The name of the author which is displayed
                                    to the viewer. This may be different to `name`.
                        * short_name    A shortened version of the author's name.
                        * type      Type of the author.
                        * url       URL for the author's channel/page.

                        * images    A list of the author's profile picture in
                                    different sizes. See below for the
                                    fields which an image may have.
                        * badges    A list of the author's badges.
                                    Mandatory fields:
                                    * title         The title of the badge.

                                    Optional fields:
                                    * id            Identifier for the badge.
                                    * name          Name of the badge.
                                    * version       Version of the badge.
                                    * icon_name     Name of the badge icon.
                                    * icons         A list of images for the badge icons.
                                                    See below for potential fields.
                                    * description   The description of the badge.
                                    * alternative_title
                                                    Alternative title of the badge.
                                    * click_action  Action to perform if the badge is clicked.
                                    * click_url     URL to visit if the badge is clicked.

                        * gender    Gender of the author.

                        The following boolean fields are self-explanatory:
                        * is_banned
                        * is_bot
                        * is_non_coworker
                        * is_original_poster
                        * is_verified


    Mandatory fields for replays/vods/clips (i.e. a video which is not live):

    time_in_seconds:    The number of seconds after the video began, that the message was sent.
    time_text:          Human-readable format for `time_in_seconds`.


    Optional fields:

    sub_message:        Additional text of the message.
    action_type:        Action type of the item.
    amount:             The amount of money which was sent with the message.
    tooltip:            Text to be displayed when hovering over the message.
    icon:               Icon associated with the message.
    target_message_id:  The identifier for a message which this message references.
    action:             The action of the message.
    viewer_is_creator:  Whether the viewer is the creator or not.

    sticker_images:     A list of the sticker image in different sizes. See
                        below for the fields which an image may have.
    sponsor_icons:      A list of the sponsor image in different sizes. See
                        below for potential fields.
    ticker_icons:       A list of the ticker image in different sizes. See
                        below for potential fields.
    ticker_duration:    How long the ticker message is displayed for.


    The following fields indicate HEX colour information for the message:

    author_name_text_colour
    timestamp_colour
    body_background_colour
    header_text_colour
    header_background_colour
    body_text_colour
    background_colour
    money_chip_text_colour
    money_chip_background_colour
    start_background_colour
    amount_text_colour
    end_background_colour
    detail_text_colour


    An image contains the following fields:
    url:                Mandatory. URL of the image.
    id:                 Mandatory. Identifier for the image.
    width:              Width of the image.
    height:             Height of the image.



    TODO
    """

    # id
    # author_id
    # author_name
    # amount
    # message
    # time_text
    # timestamp
    # author_images
    # tooltip
    # icon
    # author_badges
    # badge_icons
    # sticker_images
    # ticker_duration
    # sponsor_icons
    # ticker_icons

    # target_id
    # action
    # viewer_is_creator
    # is_stackable
    # sub_message

    _DEFAULT_INIT_PARAMS = {
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36',
            'Accept-Language': 'en-US, en'
        },

        'cookies': None,  # cookies file (optional),
        'timeout': 10
    }
    _INIT_PARAMS = _DEFAULT_INIT_PARAMS

    _DEFAULT_PARAMS = {
        'url': None,  # should be overridden
        'start_time': None,  # get from beginning (even before stream starts)
        'end_time': None,  # get until end
        #'callback': None,  # do something for every message

        'max_attempts': 30,
        'retry_timeout': 1,  # 1 second
        # TODO timeout between attempts
        'max_messages': None,

        'output': None,
        'logging': 'normal',
        'verbose': False,
        'safe_print': False,
        'pause_on_debug': False,

        # If True, program will not sleep when a timeout instruction is given
        'force_no_timeout': False,

        'force_encoding': None, # use default


        # stop getting messages after no messages have been sent for `timeout` seconds
        'timeout': None,


        'message_groups': ['messages'],  # 'all' can be chosen here
        'message_types': None,  # ['text_message'], # messages


        # YouTube only
        'chat_type': 'live',  # live or top


        # Twitch only

        # allows for keyboard interrupts to occur
        # 0.25, # try again after receiving no data after a certain time
        'message_receive_timeout': 0.1,
        'buffer_size': 4096  # default buffer size for socket
    }

    def __str__(self):
        return ''

    @staticmethod
    def must_add_item(item, message_groups_dict, messages_groups_to_add, messages_types_to_add):
        if 'all' in messages_groups_to_add: # user wants everything
            return True

        valid_message_types = []
        for message_group in messages_groups_to_add or []:
            valid_message_types += message_groups_dict.get(message_group, [])

        for message_type in messages_types_to_add or []:
            valid_message_types.append(message_type)

        return item.get('message_type') in valid_message_types

    @staticmethod
    def get_param_value(params, key):
        return params.get(key, ChatDownloader._DEFAULT_PARAMS.get(key))

    @staticmethod
    def remap(info, remapping_dict, remapping_functions, remap_key, remap_input, keep_unknown_keys = False, replace_char_with_underscores=None):
        remap = remapping_dict.get(remap_key)

        if remap:
            if isinstance(remap, tuple):
                index, mapping_function = remap
                info[index] = remapping_functions[mapping_function](
                    remap_input)
            else:
                info[remap] = remap_input
        elif keep_unknown_keys:
            if replace_char_with_underscores:
                remap_key = remap_key.replace(replace_char_with_underscores, '_')
            info[remap_key] = remap_input

        # else:
        #     pass # do nothing

    def __init__(self, updated_init_params=None):
        """Initialise a new session for making requests."""
        # self._name = None
        self._INIT_PARAMS.update(updated_init_params or {})

        self.session = requests.Session()
        self.session.headers = self._INIT_PARAMS.get('headers')

        cookies = self._INIT_PARAMS.get('cookies')
        cj = MozillaCookieJar(cookies)

        if cookies:  # is not None
            # Only attempt to load if the cookie file exists.
            if os.path.exists(cookies):
                cj.load(ignore_discard=True, ignore_expires=True)
            else:
                raise CookieError(
                    'The file "{}" could not be found.'.format(cookies))
        self.session.cookies = cj

    def update_session_headers(self, new_headers):
        self.session.headers.update(new_headers)

    def get_cookies_dict(self):
        return requests.utils.dict_from_cookiejar(self.session.cookies)

    def get_cookie_value(self, name, default=None):
        return self.get_cookies_dict().get(name, default)

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _session_post(self, url, **kwargs):
        """Make a request using the current session."""
        #print('_session_post', url, data, headers)

        # update_dict_without_overwrite
        # print('BEFORE',kwargs)
        # #new_headers = {**self.session.headers, **kwargs.get('headers',{})}
        # kwargs['headers'] = {**self.session.headers, **kwargs.get('headers',{})}
        # print('AFTER',kwargs)
        # , data=data, headers=new_headers, params=1
        return self.session.post(url, **kwargs)

    def _session_get(self, url, **kwargs):
        """Make a request using the current session."""
        return self.session.get(url, **kwargs)

    def _session_get_json(self, url, **kwargs):
        """Make a request using the current session and get json data."""
        s = self._session_get(url, **kwargs)

        try:
            return s.json()
        except JSONDecodeError:
            # TODO determine if html
            webpage_title = get_title_of_webpage(s.text)
            raise UnexpectedHTML(webpage_title, s.text)

    _VALID_URL = None
    _CALLBACK = None



    #_LIST_OF_MESSAGES = []
    # def get_chat_messages(self, params=None):
    #     pass

    def get_chat(self, params=None):
        # pass
        raise NotImplementedError

        # if params is None:
        #     params = {}

        # update_dict_without_overwrite(params, self._DEFAULT_PARAMS)
        # TODO must override
        # m = self.get_chat_messages(params)

        # return Chat(m)

    def get_tests(self):
        t = getattr(self, '_TEST', None)
        if t:
            assert not hasattr(self, '_TESTS'), \
                '%s has _TEST and _TESTS' % type(self).__name__
            tests = [t]
        else:
            tests = getattr(self, '_TESTS', [])
        for t in tests:
            yield t

    @staticmethod
    def perform_callback(callback, data, params=None):
        if params is None:
            params = {}
        if callable(callback):
            try:
                callback(data)
            except TypeError:
                raise CallbackFunction(
                    'Incorrect number of parameters for function '+callback.__name__)
        elif callback is None:
            pass  # do not perform callback
        else:
            raise CallbackFunction(
                'Unable to call callback function '+callback.__name__)

    # TODO make this a class with a __dict__ attribute

    @staticmethod
    def create_image(url, width=None, height=None, image_id=None):
        if url.startswith('//'):
            url = 'https:' + url
        image = {
            'url':  url,
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
    def move_to_dict(info, dict_name, replace_key=None, create_when_empty = False, *info_keys):
        """
        Move all items with keys that contain some text to a separate dictionary.

        These keys are modifed by removing some text.
        """
        if replace_key is None:
            replace_key = dict_name+'_'

        new_dict = {}

        keys = (info_keys or info or {}).copy()
        for key in keys:
            if replace_key in key:
                info_item = info.pop(key, None)
                new_key = key.replace(replace_key, '')

                # set it if it contains info
                if info_item not in (None, [], {}):
                    new_dict[new_key] = info_item

        if dict_name not in info and (create_when_empty or new_dict != {}):
            info[dict_name] = new_dict

        return new_dict

    @staticmethod
    def retry(attempt_number, max_attempts, retry_timeout, logging_level, pause_on_debug, text = None, error=''):
        if text is None:
            text = []
        elif not isinstance(text, (tuple, list)):
            text = [text]

        text.append('Retry #{}. {}'.format(attempt_number, error))

        is_unexpected_html = isinstance(error, UnexpectedHTML)
        must_sleep = retry_timeout>=0
        log(
            'error',
            text,
            logging_level,
            matching=('debug', 'errors'),
            pause_on_debug=(pause_on_debug and not is_unexpected_html and not must_sleep)
        )
        if is_unexpected_html:
            log(
                'error',
                error.html,
                logging_level,
                matching=('debug', 'errors'),
                pause_on_debug=pause_on_debug and not must_sleep
            )



        if attempt_number >= max_attempts:
            raise RetriesExceeded(
                'Maximum number of retries has been reached ({}).'.format(max_attempts))

        if must_sleep:
            # TODO add option for exponential retry...
            log(
                'error',
                'Sleeping for {}s.'.format(retry_timeout),
                logging_level,
                matching=('debug', 'errors'),
                pause_on_debug=pause_on_debug
            )
            time.sleep(retry_timeout)
        else:
            input('Press Enter to continue...')

    @staticmethod
    def check_for_invalid_types(messages_types_to_add, allowed_message_types):
        invalid_types = set(messages_types_to_add) - set(allowed_message_types)
        if invalid_types:
            raise InvalidParameter(
                'Invalid types specified: {}'.format(invalid_types))


    @staticmethod
    def get_mapped_keys(remapping):
        mapped_keys = set()
        for key in remapping:
            value = remapping[key]
            if isinstance(remapping[key], tuple):
                value = value[0]
            mapped_keys.add(value)
        return mapped_keys
    # def _format_item(self, result, item):
    #     # TODO fix this method

    #     # split by | not enclosed in []
    #     split = re.split(
    #         self._MESSAGE_FORMATTING_INDEXES_REGEX, result.group(2))
    #     for s in split:

    #         # check if optional formatting is there
    #         parse = re.search(self._MESSAGE_FORMATTING_FORMATTING_REGEX, s)
    #         formatting = None
    #         if(parse):
    #             index = parse.group(1)
    #             formatting = parse.group(2)
    #         else:
    #             index = s

    #         if(index in item):
    #             value = item[index]
    #             if(formatting):
    #                 if(index == 'timestamp'):
    #                     value = microseconds_to_timestamp(
    #                         item[index], format=formatting)
    #                 # possibility for more formatting options

    #                 # return value if index matches, otherwise keep searching
    #             return '{}{}{}'.format(result.group(1), value, result.group(3))

    #     return ''  # no match, return empty

    # def message_to_string(self, item, format_string='{[{time_text|timestamp[%Y-%m-%d %H:%M:%S]}]}{ ({badges})}{ *{amount}*}{ {author_name}}:{ {message}}'):
    #     """
    #     Format item for printing to standard output. The default format_string will print out as:
    #     [time] (badges) *amount* author: message\n
    #     where (badges) and *amount* are optional.
    #     """

    #     return re.sub(self._MESSAGE_FORMATTING_GROUPS_REGEX, lambda result: self._format_item(result, item), format_string)
    #     # return '[{}] {}{}{}: {}'.format(
    #     # 	item['time_text'] if 'time_text' in item else (
    #     # 		self.__microseconds_to_timestamp(item['timestamp']) if 'timestamp' in item else ''),
    #     # 	'({}) '.format(item['badges']) if 'badges' in item else '',
    #     # 	'*{}* '.format(item['amount']) if 'amount' in item else '',
    #     # 	item['author'],
    #     # 	item['message'] or ''
    #     # )

    # def print_item(self, item):
    #     print(self.message_to_string(item), flush=True)
