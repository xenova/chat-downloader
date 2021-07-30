"""Main module."""
import sys
import itertools
import time
import json

from urllib.parse import urlparse

from .metadata import __version__

from .sites.common import (
    SiteDefault,
    BaseChatDownloader
)
from .sites import get_all_sites

from .formatting.format import ItemFormatter
from .utils.core import (
    safe_print,
    get_default_args,
    update_dict_without_overwrite
)

from .utils.timed_utils import TimedGenerator

from .debugging import (
    log,
    set_testing_mode,
    TestingModes,
    TestingException
)

from .output.continuous_write import ContinuousWriter


from requests.exceptions import (
    RequestException,
    ConnectionError
)

from .errors import (
    URLNotProvided,
    SiteNotSupported,
    InvalidURL,
    ChatDownloaderError,
    ChatGeneratorError,
    ParsingError
)


class ChatDownloader():
    """Class used to create sessions and download chats."""

    def __init__(self,
                 headers=None,
                 cookies=None,
                 proxy=None,
                 ):
        """Initialise a new session for making requests. Parameters are saved
        and are sent to the relevant constructor when creating a new session.

        :param headers: Headers to use for subsequent requests, defaults to None
        :type headers: dict, optional
        :param cookies: Path of cookies file, defaults to None
        :type cookies: str, optional
        :param proxy: Use the specified HTTP/HTTPS/SOCKS proxy. To enable SOCKS
            proxy, specify a proper scheme. For example socks5://127.0.0.1:1080/.
            Pass in an empty string (--proxy "") for direct connection. Defaults
            to None
        :type proxy: str, optional
        """

        self.init_params = locals()
        self.init_params.pop('self')

        log('debug', f'Python version: {sys.version}')
        log('debug', f'Program version: {__version__}')
        log('debug', f'Initialisation parameters: {self.init_params}')

        # Track sessions using a dictionary (allows for reusing)
        self.sessions = {}

    def get_chat(self, url=None,
                 start_time=None,
                 end_time=None,
                 max_attempts=15,
                 retry_timeout=None,
                 interruptible_retry=True,
                 timeout=None,
                 inactivity_timeout=None,
                 max_messages=None,

                 message_groups=SiteDefault('message_groups'),
                 message_types=None,

                 # Output
                 output=None,
                 overwrite=True,
                 sort_keys=True,
                 indent=4,

                 # Formatting
                 format=SiteDefault('format'),
                 format_file=None,

                 # YouTube
                 chat_type='live',
                 ignore=None,

                 # Twitch
                 message_receive_timeout=0.1,
                 buffer_size=4096
                 ):
        """Used to get chat messages from a livestream, video, clip or past broadcast.

        :param url: The URL of the livestream, video, clip or past broadcast,
            defaults to None
        :type url: str, optional
        :param start_time: Start time in seconds or hh:mm:ss, defaults
            to None (as early as possible)
        :type start_time: float, optional
        :param end_time: End time in seconds or hh:mm:ss, defaults to
            None (until the end)
        :type end_time: float, optional
        :param max_attempts: Maximum number of attempts to retrieve chat
            messages, defaults to 15
        :type max_attempts: int, optional
        :param retry_timeout: Number of seconds to wait before retrying. Setting
            this to a negative number will wait for user input. Default is None
            (use exponential backoff, i.e. immediate, 1s, 2s, 4s, 8s, ...)
        :type retry_timeout: float, optional
        :param interruptible_retry: Have the option to skip waiting and
            immediately retry. Defaults to True
        :type interruptible_retry: bool, optional
        :param timeout: Stop retrieving chat after a certain duration
            (in seconds), defaults to None
        :type timeout: float, optional
        :param inactivity_timeout: Stop getting messages after not receiving
            anything for a certain duration (in seconds), defaults to None
        :type inactivity_timeout: float, optional
        :param max_messages: Maximum number of messages to retrieve, defaults
            to None (unlimited)
        :type max_messages: int, optional
        :param message_groups: List of messages groups (a predefined,
            site-specific collection of message types) to include
        :type message_groups: SiteDefault, optional
        :param message_types: List of messages types to include, defaults to None
        :type message_types: list, optional
        :param output: Path of the output file, defaults to None (print to
            standard output)
        :type output: str, optional
        :param overwrite: If True, overwrite output file. Otherwise, append
            to the end of the file. Defaults to True. In both cases, the file
            (and directories) is created if it does not exist.
        :type overwrite: bool, optional
        :param sort_keys: Sort keys when outputting to a file, defaults to True
        :type sort_keys: bool, optional
        :param indent: Number of spaces to indent JSON objects by. If
            nonnumerical input is provided, this will be used to indent
            the objects. Defaults to 4
        :type indent: Union[int, str], optional
        :param format: Specify how messages should be formatted for printing,
            defaults to the site's default value
        :type format: SiteDefault, optional
        :param format_file: Specify the path of the format file to choose
            formats from, defaults to None
        :type format_file: str, optional
        :param chat_type: Specify chat type, defaults to 'live'
        :type chat_type: str, optional
        :param ignore: Ignore a list of video ids, defaults to None
        :type ignore: list, optional
        :param message_receive_timeout: Time before requesting for new messages,
            defaults to 0.1
        :type message_receive_timeout: float, optional
        :param buffer_size: Specify a buffer size for retrieving messages,
            defaults to 4096
        :type buffer_size: int, optional
        :raises URLNotProvided: if no URL is provided
        :raises ChatGeneratorError: if no valid generator can be found for a site
        :raises SiteNotSupported: if no matching site can be found
        :raises InvalidURL: if the URL provided is not valid
        :return: The appropriate Chat object, given these parameters
        :rtype: Chat
        """

        # TODO params to add
        # If True, program will not sleep when a timeout instruction is given
        # force_no_timeout=False,
        # :param force_no_timeout: Force no timeout between subsequent requests
        #  force_encoding=None, # use default

        if not url:
            raise URLNotProvided('No URL provided.')

        original_params = locals()
        original_params.pop('self')

        # loop through all websites and
        # get corresponding website parser
        # based on matching url with predefined regex
        for site in get_all_sites():
            match_info = site.matches(url)
            if match_info:  # match found

                function_name, match = match_info

                # Create new session
                self.create_session(site)
                site_object = self.sessions[site.__name__]

                # Parse site-defaults
                params = {}
                for k, v in original_params.items():
                    params[k] = site_object.get_site_value(v)

                log('info', f'Site: {site_object._NAME}')
                log('debug', f'Program parameters: {params}')

                get_chat = getattr(site_object, function_name, None)
                if not get_chat:
                    raise NotImplementedError(
                        f'{function_name} has not been implemented in {site.__name__}.')

                chat = get_chat(match, params)
                log('debug',
                    f'Match found: "{match}". Running "{function_name}" function in "{site.__name__}".')

                if chat is None:
                    raise ChatGeneratorError(
                        f'No valid generator found in {site.__name__} for url "{url}"')

                if isinstance(params['max_messages'], int):
                    chat.chat = itertools.islice(
                        chat.chat, params['max_messages'])
                else:
                    pass  # TODO throw error

                if params['timeout'] is not None or params['inactivity_timeout'] is not None:
                    # Generator requires timing functionality

                    chat.chat = TimedGenerator(
                        chat.chat, params['timeout'], params['inactivity_timeout'])

                    if isinstance(params['timeout'], (float, int)):
                        start = time.time()

                        def log_on_timeout():
                            log('debug',
                                f'Timeout occurred after {time.time() - start} seconds.')
                        setattr(chat.chat, 'on_timeout', log_on_timeout)

                    if isinstance(params['inactivity_timeout'], (float, int)):
                        def log_on_inactivity_timeout():
                            log('debug',
                                f"Inactivity timeout occurred after {params['inactivity_timeout']} seconds.")
                        setattr(chat.chat, 'on_inactivity_timeout',
                                log_on_inactivity_timeout)

                formatter = ItemFormatter(params['format_file'])
                chat.format = lambda x: formatter.format(
                    x, format_name=params['format'])

                if params['output']:
                    chat.attach_writer(ContinuousWriter(
                        params['output'],
                        indent=params['indent'],
                        sort_keys=params['sort_keys'],
                        overwrite=params['overwrite'],
                        lazy_initialise=True
                    ))

                chat.site = site_object

                log('debug', f'Chat information: {chat.__dict__}')
                log('info', f'Retrieving chat for "{chat.title}".')

                return chat

        parsed = urlparse(url)
        log('debug', str(parsed))

        if parsed.netloc:
            raise SiteNotSupported(f'Site not supported: {parsed.netloc}')
        elif not parsed.scheme:  # No scheme, try to correct
            original_params['url'] = 'https://' + url
            chat = self.get_chat(**original_params)
            if chat:
                return chat
        else:
            raise InvalidURL(f'Invalid URL: "{url}"')

    def create_session(self, chat_downloader_class, overwrite=False):
        if not issubclass(chat_downloader_class, BaseChatDownloader):
            raise TypeError(
                f'Unable to create session, class must extend BaseChatDownloader. Class given: {chat_downloader_class}')
        elif chat_downloader_class == BaseChatDownloader:
            raise TypeError(
                'Unable to create session, class may not be BaseChatDownloader.')

        session_name = chat_downloader_class.__name__
        log('debug', f'Created {session_name} session.')

        if session_name not in self.sessions or overwrite:
            self.sessions[session_name] = chat_downloader_class(
                **self.init_params)

        return self.sessions[session_name]

    def get_session(self, chat_downloader_class):
        return self.sessions.get(chat_downloader_class.__name__)

    def close(self):
        """Close all sessions associated with the object"""
        for session in self.sessions.values():
            session.close()

        self.sessions = {}


def run(propagate_interrupt=False, **kwargs):
    """
    Create a single session and get the chat using the specified parameters.
    """

    # Set testing mode
    if kwargs.get('exit_on_debug'):
        set_testing_mode(TestingModes.EXIT_ON_DEBUG)
    elif kwargs.get('pause_on_debug'):
        set_testing_mode(TestingModes.PAUSE_ON_DEBUG)

    init_param_names = get_default_args(ChatDownloader.__init__)
    program_param_names = get_default_args(ChatDownloader.get_chat)

    update_dict_without_overwrite(kwargs, init_param_names)
    update_dict_without_overwrite(kwargs, program_param_names)

    chat_params = {}
    init_params = {}

    for arg in kwargs:
        value = kwargs[arg]

        if arg in program_param_names:
            chat_params[arg] = value
        elif arg in init_param_names:
            init_params[arg] = value

    downloader = ChatDownloader(**init_params)

    try:
        chat = downloader.get_chat(**chat_params)

        if kwargs.get('quiet'):  # Only check if quiet once
            def callback(item):
                pass
        else:
            def callback(item):
                chat.print_formatted(item)

        for message in chat:
            callback(message)

        log('info', 'Finished retrieving chat messages.')

    except (
        ChatGeneratorError,
        ParsingError,
        TestingException
    ) as e:  # Errors which may be bugs
        log('error', f'{e}. Please report this at https://github.com/xenova/chat-downloader/issues/new/choose')

    except ChatDownloaderError as e:  # Expected errors
        log('error', e)

    except ConnectionError as e:
        log(
            'error', f'Unable to establish a connection. Please check your internet connection. {e}')

    except RequestException as e:
        log('error', e)

    except KeyboardInterrupt as e:
        if propagate_interrupt:
            raise e
        else:
            log('error', 'Keyboard Interrupt')

    finally:
        downloader.close()
