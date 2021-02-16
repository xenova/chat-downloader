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
    log,
    get_logger,
    safe_print,
    set_log_level,
    get_default_args,
    update_dict_without_overwrite,
    TimedGenerator
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
        """
        Initialise a new session for making requests.

        :param headers: Test headers
        :param cookies: Path of cookies file
        :param proxy: Use the specified HTTP/HTTPS/SOCKS proxy. To enable SOCKS proxy, specify a proper scheme. For example socks5://127.0.0.1:1080/. Pass in an empty string (--proxy "") for direct connection. Default is None (i.e. do not use a proxy)

        """
        self.init_params = locals()
        self.init_params.pop('self')

        # Track a dict of sessions
        self.sessions = {}

    def get_chat(self, url=None,
                 start_time=None,
                 end_time=None,
                 max_attempts=15,  # ~ 2^15s ~ 9 hours
                 retry_timeout=None,
                 timeout=None,
                 max_messages=None,

                 logging='info',
                 pause_on_debug=False,
                 exit_on_debug=False,

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
        :param exit_on_debug: Exit when something unexpected happens
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
                info = self.sessions[site.__name__].get_chat(**params)
                if isinstance(max_messages, int):
                    info.chat = itertools.islice(info.chat, max_messages)

                if timeout is not None or inactivity_timeout is not None:
                    # Generator requires timing functionality

                    info.chat = TimedGenerator(
                        info.chat, timeout, inactivity_timeout)

                    if isinstance(timeout, (float, int)):
                        start = time.time()

                        def log_on_timeout():
                            log('debug', 'Timeout occurred after {} seconds.'.format(
                                time.time() - start))
                        setattr(info.chat, 'on_timeout', log_on_timeout)

                    if isinstance(inactivity_timeout, (float, int)):
                        def log_on_inactivity_timeout():
                            log('debug', 'Inactivity timeout occurred after {} seconds.'.format(
                                inactivity_timeout))
                        setattr(info.chat, 'on_inactivity_timeout',
                                log_on_inactivity_timeout)

                info.site = self.sessions[site.__name__]

                formatter = ItemFormatter(params['format_file'])
                info.format = lambda x: formatter.format(
                    x, format_name=params['format'])

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
        for session in self.sessions.values():
            session.close()

        self.sessions = {}


def run(**kwargs):
    """
    Create a single session and get the chat using the specified parameters.

    e.g.
    >>> run(url='https://www.youtube.com/watch?v=5qap5aO4i9A')

    """

    init_param_names = get_default_args(ChatDownloader.__init__)
    program_param_names = get_default_args(ChatDownloader.get_chat)

    update_dict_without_overwrite(kwargs, init_param_names)
    update_dict_without_overwrite(kwargs, program_param_names)

    if kwargs.get('testing'):
        kwargs['logging'] = 'debug'
        kwargs['pause_on_debug'] = True
        # args.message_groups = 'all'
        # program_params['timeout = 180

    if kwargs.get('verbose'):
        kwargs['logging'] = 'debug'

    quiet = kwargs.get('quiet')
    if quiet or kwargs['logging'] == 'none':
        get_logger().disabled = True
    else:
        set_log_level(kwargs['logging'])

    output = kwargs.get('output')

    chat_params = {}
    init_params = {}

    for arg in kwargs:
        value = kwargs[arg]

        if arg in program_param_names:
            chat_params[arg] = value
        elif arg in init_param_names:
            init_params[arg] = value

    log('debug', 'Python version: {}'.format(sys.version))
    log('debug', 'Program version: {}'.format(__version__))

    log('debug', 'Initialisation parameters: {}'.format(init_params))

    downloader = ChatDownloader(**init_params)

    output_file = None
    try:
        chat = downloader.get_chat(**chat_params)

        log('debug', 'Chat information: {}'.format(chat.__dict__))
        log('info', 'Retrieving chat for "{}".'.format(chat.title))

        def print_formatted(item):
            if not quiet:
                formatted = chat.format(item)
                safe_print(formatted)

        if output:
            output_args = {
                k: kwargs.get(k) for k in ('indent', 'sort_keys', 'overwrite')
            }
            output_file = ContinuousWriter(output, **output_args)

            def write_to_file(item):
                print_formatted(item)
                output_file.write(item, flush=True)

            callback = write_to_file
        else:
            callback = print_formatted

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

        if output and output_file:
            output_file.close()
