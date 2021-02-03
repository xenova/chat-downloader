"""Console script for chat_downloader."""
import argparse
import sys
import re
from docstring_parser import parse as doc_parse
from requests.exceptions import RequestException

import chat_downloader
from .chat_downloader import ChatDownloader
from .output.continuous_write import ContinuousWriter

from .utils import (
    log,
    get_logger,
    safe_print,
    set_log_level,
    get_default_args
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
    NoContinuation,
    TimeoutException
)


def main():

    parser = argparse.ArgumentParser(
        description='A simple tool used to retrieve chat messages from livestreams, videos, clips and past broadcasts. No authentication needed!',
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument('--version', action='version',
                        version=chat_downloader.__version__)

    # PROGRAM PARAMS
    parser.add_argument(
        'url', help='The URL of the livestream, video, clip or past broadcast')

    def get_info(function):
        info = {}

        docstring = doc_parse(function.__doc__)
        args = get_default_args(function)

        for param in docstring.params:
            info[param.arg_name] = {
                # + '\n' + '(default: {})'.format(args.get(param.arg_name))
                'help': param.description,
                'default': args.get(param.arg_name)
            }
        return info

    # get help and default info
    get_chat_info = get_info(ChatDownloader.get_chat)
    get_init_info = get_info(ChatDownloader.__init__)

    def add_param(param_type, group, *keys, **kwargs):

        info = get_chat_info if param_type == 'chat' else get_init_info
        key = keys[0].lstrip('-')
        group.add_argument(*keys,
                           **info[key],  # add defaults and help
                           **kwargs
                           )

    def add_chat_param(group, *keys, **kwargs):
        add_param('chat', group, *keys, **kwargs)

    def add_init_param(group, *keys, **kwargs):
        add_param('init', group, *keys, **kwargs)

    time_group = parser.add_argument_group('Timing Arguments')

    add_chat_param(time_group, '--start_time', '-s')
    add_chat_param(time_group, '--end_time', '-e')

    def splitter(s):
        return [item.strip() for item in re.split(r'[\s,;]+', s)]

    # Specify message types/groups
    type_group = parser.add_argument_group('Message Type Arguments')
    type_options = type_group.add_mutually_exclusive_group()

    add_chat_param(type_options, '--message_types', type=splitter)
    add_chat_param(type_options, '--message_groups', type=splitter)

    def try_parse_int(text):
        try:
            return int(text)
        except Exception:
            return text

    retry_group = parser.add_argument_group(
        'Retry Arguments')  # what to do when an error occurs
    add_chat_param(retry_group, '--max_attempts', type=int)
    add_chat_param(retry_group, '--retry_timeout', type=float)

    termination_group = parser.add_argument_group('Termination Arguments')
    add_chat_param(termination_group, '--max_messages', type=int)
    add_chat_param(
        termination_group, '--inactivity_timeout', type=float)
    add_chat_param(termination_group, '--timeout', type=float)

    # TODO request_timeout
    # specify how long to spend on any single http request

    # TODO
    # parser.add_argument('--force_encoding', default=default_params['force_encoding'],
    #                     help='force certain encoding\n(default: %(default)s)')

    # Formatting
    format_group = parser.add_argument_group('Format Arguments')
    add_chat_param(format_group, '--format')
    add_chat_param(format_group, '--format_file')

    # info = get_site_info(YouTubeChatDownloader)
    youtube_group = parser.add_argument_group(
        '[Site Specific] YouTube Arguments')
    add_chat_param(youtube_group, '--chat_type',
                   choices=['live', 'top'])
    # add_chat_param(
    #     youtube_group, '--force_no_timeout', action='store_true')

    # info = get_site_info(TwitchChatDownloader)
    twitch_group = parser.add_argument_group(
        '[Site Specific] Twitch Arguments')
    add_chat_param(
        twitch_group, '--message_receive_timeout', type=float)
    add_chat_param(twitch_group, '--buffer_size', type=int)

    output_group = parser.add_argument_group('Output Arguments')
    output_group.add_argument(
        '--output', '-o', help='Path of the output file, default is None (i.e. print to standard output)', default=None)
    output_group.add_argument(
        '--sort_keys', help='Sort keys when outputting to a file', action='store_false')
    output_group.add_argument('--indent', type=try_parse_int,
                              help='Number of spaces to indent JSON objects by. If nonnumerical input is provided, this will be used to indent the objects.', default=4)
    output_group.add_argument(
        '--overwrite', help='Overwrite output file if it exists. Otherwise, append to the end of the file.', action='store_true')

    debug_group = parser.add_argument_group('Debugging/Testing Arguments')
    add_chat_param(debug_group, '--pause_on_debug')

    debug_options = debug_group.add_mutually_exclusive_group()
    add_chat_param(debug_options, '--logging',
                   choices=['none', 'debug', 'info', 'warning', 'error', 'critical'])

    debug_options.add_argument(
        '--testing', help='Enable testing mode', action='store_true')
    debug_options.add_argument(
        '--verbose', '-v', help='Print various debugging information. This is equivalent to setting logging to debug', action='store_true')
    debug_options.add_argument(
        '--quiet', '-q', help='Activate quiet mode (hide all output)', action='store_true')

    # INIT PARAMS
    init_group = parser.add_argument_group('Initialisation Arguments')
    add_init_param(init_group, '--cookies', '-c')
    # TODO add headers (user agent) as arg

    parser._positionals.title = 'Mandatory Arguments'
    parser._optionals.title = 'General Arguments'

    args = parser.parse_args()

    # TODO DEBUGGING:
    # args.testing = True

    if args.testing:
        args.logging = 'debug'
        args.pause_on_debug = True
        # args.message_groups = 'all'
        # program_params['timeout = 180

    if args.verbose:
        args.logging = 'debug'

    if args.quiet or args.logging == 'none':
        get_logger().disabled = True
    else:
        set_log_level(args.logging)

    chat_params = {
        k: getattr(args, k, None)
        for k in get_chat_info
    }

    init_params = {
        k: getattr(args, k, None)
        for k in get_init_info
    }

    downloader = ChatDownloader(**init_params)

    output_file = None
    try:
        log('debug', 'Python version: {}'.format(sys.version))
        log('debug', 'Program version: {}'.format(chat_downloader.__version__))

        chat = downloader.get_chat(**chat_params)

        log('debug', 'Chat information: {}'.format(chat.__dict__))
        log('info', 'Retrieving chat for "{}".'.format(chat.title))

        def print_formatted(item):
            if not args.quiet:
                formatted = chat.format(item)
                safe_print(formatted)

        if args.output:
            output_args = {
                k: getattr(args, k, None) for k in ('indent', 'sort_keys', 'overwrite')
            }
            output_file = ContinuousWriter(
                args.output, **output_args)

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
        RetriesExceeded
    ) as e:
        log('error', e)
        # log('error', e, logging_level)  # always show
        # '{} ({})'.format(, e.__class__.__name__)

    except NoContinuation as e:
        log('info', e)

    except RequestException as e:
        log('error', 'Unable to establish a connection. Please check your internet connection. {}'.format(e))
        # log('error', e)  # traceback.format_exc()
        # TODO if e instance of (no internet connection)...
    except TimeoutException as e:
        log('info', e)

    except KeyboardInterrupt:
        log('error', 'Keyboard Interrupt')

    finally:
        downloader.close()

        if args.output and output_file:
            output_file.close()
