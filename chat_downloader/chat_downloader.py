"""Main module."""
import sys
import re
import itertools
import time

from urllib.parse import urlparse

from .metadata import __version__

from .sites.common import SiteDefault
from .sites import get_all_sites

from .formatting.format import ItemFormatter
from .utils import (
    safe_print,
    get_default_args,
    update_dict_without_overwrite,
    TimedGenerator
)

from .debugging import (
    log,
    disable_logger,
    set_log_level
)

from .output.continuous_write import ContinuousWriter


from requests.exceptions import (
    RequestException,
    ConnectionError
)

from .errors import (
    URLNotProvided,
    SiteNotSupported,
    LoginRequired,
    VideoUnavailable,
    NoChatReplay,
    VideoUnplayable,
    InvalidParameter,
    InvalidURL,
    RetriesExceeded,
    NoContinuation
)


class ChatDownloader():

    def __init__(self,
                 headers=None,
                 cookies=None,
                 proxy=None,
                 ):
        """Initialise a new session for making requests. Parameters are saved
        and are sent to the constructor when creating a new session.

        :param headers: Headers to use for subsequent requests, defaults to None
        :type headers: dict, optional
        :param cookies: Path of cookies file, defaults to None
        :type cookies: str, optional
        :param proxy: Use the specified HTTP/HTTPS/SOCKS proxy. To enable SOCKS proxy,
            specify a proper scheme. For example socks5://127.0.0.1:1080/. Pass in an
            empty string (--proxy "") for direct connection. Default to None
        :type proxy: str, optional
        """

        self.init_params = locals()
        self.init_params.pop('self')

        log('debug', 'Python version: {}'.format(sys.version))
        log('debug', 'Program version: {}'.format(__version__))
        log('debug', 'Initialisation parameters: {}'.format(self.init_params))

        # Track sessions using a dictionary (allows for reusing)
        self.sessions = {}

    def get_chat(self, url=None,
                 start_time=None,
                 end_time=None,
                 max_attempts=15,
                 retry_timeout=None,
                 timeout=None,
                 max_messages=None,
                 logging='info',
                 pause_on_debug=False,
                 exit_on_debug=False,
                 inactivity_timeout=None,
                 message_groups=SiteDefault('message_groups'),
                 message_types=None,

                 # Output
                 output=None,
                 overwrite=False,
                 sort_keys=True,
                 indent=4,

                 # Formatting
                 format=SiteDefault('format'),
                 format_file=None,

                 # YouTube
                 chat_type='live',

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
        :param timeout: Stop retrieving chat after a certain duration (in seconds),
            defaults to None
        :type timeout: float, optional
        :param max_messages: Maximum number of messages to retrieve, defaults
            to None (unlimited)
        :type max_messages: int, optional
        :param logging: Level of logging to display, defaults to 'info'
        :type logging: str, optional
        :param pause_on_debug: Pause on certain debug messages, defaults to False
        :type pause_on_debug: bool, optional
        :param exit_on_debug: Exit when something unexpected happens, defaults to False
        :type exit_on_debug: bool, optional
        :param inactivity_timeout: Stop getting messages after not receiving
            anything for a certain duration (in seconds), defaults to None
        :type inactivity_timeout: float, optional
        :param message_groups: List of messages groups (a predefined,
            site-specific collection of message types) to include
        :type message_groups: SiteDefault, optional
        :param message_types: List of messages types to include, defaults to None
        :type message_types: list, optional
        :param output: Path of the output file, defaults to None (print to standard output)
        :type output: str, optional
        :param overwrite: Overwrite output file if it exists. Otherwise, append to the end of the file. Defaults to False
        :type overwrite: bool, optional
        :param sort_keys: Sort keys when outputting to a file, defaults to True
        :type sort_keys: bool, optional
        :param indent: Number of spaces to indent JSON objects by. If nonnumerical input is provided, this will be used to indent the objects. Defaults to 4
        :type indent: Union[int, str], optional
        :param format: Specify how messages should be formatted for printing,
            defaults to the site's default value
        :type format: SiteDefault, optional
        :param format_file: Specify the path of the format file to choose formats
            from, defaults to None
        :type format_file: str, optional
        :param chat_type: Specify chat type, defaults to 'live'
        :type chat_type: str, optional
        :param message_receive_timeout: Time before requesting for new messages,
            defaults to 0.1
        :type message_receive_timeout: float, optional
        :param buffer_size: Specify a buffer size for retrieving messages,
            defaults to 4096
        :type buffer_size: int, optional
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
            regex = getattr(site, '_VALID_URL')
            if isinstance(regex, str) and re.search(regex, url):  # regex has been set (not None)

                # Create new session if not already created
                if site.__name__ not in self.sessions:
                    self.sessions[site.__name__] = site(**self.init_params)

                # Parse site-defaults
                params = {}
                for k, v in original_params.items():
                    params[k] = self.sessions[site.__name__].get_site_value(v)

                log('info', 'Site: {}'.format(
                    self.sessions[site.__name__]._NAME))
                log('debug', 'Program parameters: {}'.format(params))
                chat = self.sessions[site.__name__].get_chat(**params)
                if isinstance(max_messages, int):
                    chat.chat = itertools.islice(chat.chat, max_messages)

                if timeout is not None or inactivity_timeout is not None:
                    # Generator requires timing functionality

                    chat.chat = TimedGenerator(
                        chat.chat, timeout, inactivity_timeout)

                    if isinstance(timeout, (float, int)):
                        start = time.time()

                        def log_on_timeout():
                            log('debug', 'Timeout occurred after {} seconds.'.format(
                                time.time() - start))
                        setattr(chat.chat, 'on_timeout', log_on_timeout)

                    if isinstance(inactivity_timeout, (float, int)):
                        def log_on_inactivity_timeout():
                            log('debug', 'Inactivity timeout occurred after {} seconds.'.format(
                                inactivity_timeout))
                        setattr(chat.chat, 'on_inactivity_timeout',
                                log_on_inactivity_timeout)

                if output:
                    output_file = ContinuousWriter(
                        output, indent=indent, sort_keys=sort_keys, overwrite=overwrite)

                    def write_to_file(item):
                        output_file.write(item, flush=True)

                    chat.callback = write_to_file

                chat.site = self.sessions[site.__name__]

                formatter = ItemFormatter(format_file)

                def f(item):
                    return formatter.format(item, format_name=format)
                chat.format = f

                log('debug', 'Chat information: {}'.format(chat.__dict__))
                log('info', 'Retrieving chat for "{}".'.format(chat.title))

                return chat

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
        """Close all sessions associated with the object"""
        for session in self.sessions.values():
            session.close()

        self.sessions = {}


def run(testing=False, **kwargs):
    """
    Create a single session and get the chat using the specified parameters.
    """

    init_param_names = get_default_args(ChatDownloader.__init__)
    program_param_names = get_default_args(ChatDownloader.get_chat)

    update_dict_without_overwrite(kwargs, init_param_names)
    update_dict_without_overwrite(kwargs, program_param_names)

    if testing:
        kwargs['logging'] = 'debug'
        kwargs['pause_on_debug'] = True

    if kwargs.get('verbose'):
        kwargs['logging'] = 'debug'

    quiet = kwargs.get('quiet')
    if quiet or kwargs['logging'] == 'none':
        disable_logger()
    else:
        set_log_level(kwargs['logging'])

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

        if quiet:  # Only check if quiet once
            def callback(item):
                pass
        else:
            def callback(item):
                safe_print(chat.format(item))

        for message in chat:
            callback(message)

        log('info', 'Finished retrieving chat{}.'.format(
            '' if chat.is_live else ' replay'))

    except (
        URLNotProvided,
        SiteNotSupported,
        LoginRequired,
        VideoUnavailable,
        NoChatReplay,
        VideoUnplayable,
        InvalidParameter,
        InvalidURL,
        RetriesExceeded,
        NoContinuation
    ) as e:  # Expected errors
        log('error', e)
        # log('error', e, logging_level)  # always show
        # '{} ({})'.format(, e.__class__.__name__)

    except ConnectionError as e:
        log('error', 'Unable to establish a connection. Please check your internet connection. {}'.format(e))

    except RequestException as e:
        log('error', e)

    except KeyboardInterrupt as e:
        if kwargs.get('interruptible'):
            raise e
        else:
            log('error', 'Keyboard Interrupt')

    finally:
        downloader.close()
