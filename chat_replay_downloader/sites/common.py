
import requests
from http.cookiejar import MozillaCookieJar, LoadError
import os

from ..errors import (
    CookieError,
    ParsingError,
    JSONParseError,
    CallbackFunction
)

from ..utils import (
    get_title_of_webpage,
    update_dict_without_overwrite
)


from json import JSONDecodeError


class ChatDownloader:
    """
    Subclasses of this should re-define the get_chat_messages()
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
        'messages': [],  # list of messages to append to
        'start_time': None,  # get from beginning (even before stream starts)
        'end_time': None,  # get until end
        'callback': None,  # do something for every message

        'max_attempts': 30,
        'retry_timeout':1, # 1 second
        # TODO timeout between attempts
        'max_messages': None,

        'output': None,
        'logging': 'normal',
        'safe_print': False,
        'pause_on_error': False,

        # If True, program will not sleep when a timeout instruction is given
        'force_no_timeout': False,


        # stop getting messages after no messages have been sent for `timeout` seconds
        'timeout': None,


        'message_groups': ['messages'],  # 'all' can be chosen here
        'message_types': None,  # ['text_message'], # messages
        # ,'superchat'


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
    def get_param_value(params, key):
        return params.get(key, ChatDownloader._DEFAULT_PARAMS.get(key))

    @staticmethod
    def remap(info, remapping_dict, remapping_functions, remap_key, remap_input):
        remap = remapping_dict.get(remap_key)

        if(remap):
            if(isinstance(remap, tuple)):
                index, mapping_function = remap
                info[index] = remapping_functions[mapping_function](
                    remap_input)
            else:
                info[remap] = remap_input
        # else:
        #     pass # do nothing

    def __init__(self, updated_init_params={}):
        """Initialise a new session for making requests."""
        # self._name = None
        self._INIT_PARAMS.update(updated_init_params)

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
            # print(s.text)
            webpage_title = get_title_of_webpage(s.text)
            raise JSONParseError(webpage_title)

    _VALID_URL = None
    _CALLBACK = None

    #_LIST_OF_MESSAGES = []
    def get_chat_messages(self, params={}):
        # def get_chat_messages(self, url, list_of_messages = []):
        """
        Returns a list of chat messages. To be redefined in subclasses.

        `params` should update its `messages` atttribute to allow for messages to still be
        returned after an exception is raised.
        """

        update_dict_without_overwrite(params, self._DEFAULT_PARAMS)
        # temp = params.copy()
        # params.update()
        # params.update(temp)
        # self._PARAMS.update()
        # params.update(self._PARAMS)

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
    def perform_callback(callback, data, params={}):
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
        image = {
            'url': url
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
    def create_author_info(info, *author_info_keys):
        """Move all author information to an author dictionary."""
        if 'author' not in info:
            info['author'] = {}
        # author_info_keys = ('is_author_banned', 'is_author_banned',
        #                 'is_author_original_poster', 'is_author_bot', 'is_author_non_coworker')
        for key in author_info_keys:
            author_info_item = info.pop(key, None)
            new_key = key.replace('author_', '')
            if author_info_item not in (None, [], {}): # set it if it contains info
                info['author'][new_key] = author_info_item
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
