"""Console script for chat_replay_downloader."""
import argparse
import sys
import os
import codecs
import json
import traceback
import itertools
import time

from requests.exceptions import RequestException

from .chat_replay_downloader import *

from .sites.common import BaseChatDownloader
from .output.continuous_write import ContinuousWriter

from .utils import (
    log,
    get_logger,
    safe_print,
    set_log_level
)

from .formatting.format import ItemFormatter


def main():

    default_init_params = BaseChatDownloader._DEFAULT_INIT_PARAMS
    default_params = BaseChatDownloader._DEFAULT_PARAMS

    parser = argparse.ArgumentParser(
        description='A simple tool used to retrieve chat messages from livestreams, videos, clips and past broadcasts. No authentication needed!',
        formatter_class=argparse.RawTextHelpFormatter)

    # PROGRAM PARAMS
    parser.add_argument('url', help='The URL of the livestream, video, clip or past broadcast')

    time_group = parser.add_argument_group('Timing Arguments')
    time_group.add_argument('--start_time', '-s', default=default_params['start_time'],
                            help='Set start time in seconds or hh:mm:ss\n(default: %(default)s)')
    time_group.add_argument('--end_time', '-e', default=default_params['end_time'],
                            help='Set end time in seconds or hh:mm:ss\n(default: %(default)s = until the end)')


    def splitter(s):
        return [item.strip() for item in re.split('[\s,;]+', s)]

    # Specify message types/groups
    type_group = parser.add_argument_group('Message Type Arguments')
    type_options = type_group.add_mutually_exclusive_group()

    type_options.add_argument('--message_types', type=splitter, default=default_params['message_types'],
                       help='Specify a comma-separated list of messages types to include\n(default: %(default)s)')
    type_options.add_argument('--message_groups', type=splitter, default=default_params['message_groups'],
                       help='Specify a comma-separated list of messages groups (a predefined, site-specific collection of message types) to include\n(default: %(default)s)')


    output_group = parser.add_argument_group('Output Arguments')
    output_group.add_argument('--output', '-o', default=default_params['output'],
                              help='Path of the output file\n(default: %(default)s = print to standard output)')

    debug_group = parser.add_argument_group('Debug Arguments')
    debug_group.add_argument('--pause_on_debug', default=default_params['pause_on_debug'],
                             help='Pause on certain debug messages\n(default: %(default)s)')

    debug_options = debug_group.add_mutually_exclusive_group()

    debug_options.add_argument('--logging', choices=['none', 'debug', 'info', 'warning', 'error', 'critical'], default=default_params['logging'],
                               help='Level of logging to show\n(default: %(default)s)')

    debug_options.add_argument('--testing', action='store_true', default=default_params['testing'],
                               help='Enable testing mode\n(default: %(default)s)')

    debug_options.add_argument('--verbose', '-v', action='store_true', default=default_params['verbose'],
                               help='Print various debugging information. This is equivalent to setting logging to debug\n(default: %(default)s)')

    # parser.add_argument('--safe_print', action='store_true', default=default_params['safe_print'],
    #                     help='level of logging to show\n(default: %(default)s)')

    retry_group = parser.add_argument_group('Retry Arguments') # what to do when an error occurs
    retry_group.add_argument('--max_attempts', type=int, default=default_params['max_attempts'],
                        help='Maximum number of attempts to retrieve chat messages\n(default: %(default)s)')

    retry_group.add_argument('--retry_timeout', type=float, default=default_params['retry_timeout'],
                        help='Number of seconds to wait before retrying. Setting this to a negative number will wait for user input\n(default: %(default)s = use exponential backoff, i.e. immediate, 1s, 2s, 4s, 8s, ...)')

    termination_group = parser.add_argument_group('Termination Arguments')

    termination_group.add_argument('--max_messages', type=int, default=default_params['max_messages'],
                        help='Maximum number of messages to retrieve\n(default: %(default)s = unlimited)')

    termination_group.add_argument('--inactivity_timeout', type=float, default=default_params['inactivity_timeout'],
                        help='Stop getting messages after not receiving anything for a certain duration (in seconds)\n(default: %(default)s)')

    termination_group.add_argument('--timeout', type=float, default=default_params['timeout'],
                        help='Stop retrieving chat after a certain duration (in seconds)\n(default: %(default)s)')


    # TODO request_timeout
    # specify how long to spend on any single http request

    # TODO
    # parser.add_argument('--force_encoding', default=default_params['force_encoding'],
    #                     help='force certain encoding\n(default: %(default)s)')

    # Formatting
    format_group = parser.add_argument_group('Format Arguments')
    format_group.add_argument('--format', default=default_params['format'],
                              help='Specify how messages should be formatted for printing\n(default: %(default)s = use site default)')
    format_group.add_argument('--format_file', default=default_params['format_file'],
                              help='Specify the format file to choose formats from\n(default: %(default)s)')


    # parent_group = parser.add_argument_group('parent')
    # # child_group = parent_group.add_argument_group('child')
    # parent_group.add_argument('--test', default=1,
    #                     help='wy]\n(default: %(default)s)')



    parser.add_argument('--chat_type', choices=['live', 'top'], default=default_params['chat_type'],
                        help='Specify chat type [YouTube only]\n(default: %(default)s)')

    parser.add_argument('--message_receive_timeout', type=float, default=default_params['message_receive_timeout'],
                        help='Time before requesting for new messages [Twitch only]\n(default: %(default)s)')

    parser.add_argument('--buffer_size', type=int, default=default_params['buffer_size'],
                        help='Specify a buffer size for retrieving messages [Twitch only]\n(default: %(default)s)')


    parser.add_argument('--force_no_timeout', action='store_true', default=default_params['force_no_timeout'],
                        help='Force no timeout between subsequent requests\n(default: %(default)s)')



    # INIT PARAMS
    init_group = parser.add_argument_group('Initialisation Arguments')
    init_group.add_argument('--cookies', '-c', default=default_init_params['cookies'],
                            help='Name of cookies file\n(default: %(default)s)')


    parser._positionals.title = 'Mandatory Arguments'
    parser._optionals.title = 'General Arguments'

    # TODO add fields argument
    # only retrieve data asked for
    # optimise so that only required calculations are made

    # normal = just print the messages
    # none = completely hide output
    # debug = show a lot more information

    args = parser.parse_args()

    program_params = {}  # default_params.copy()
    init_params = {}  # default_init_params.copy()

    args_dict = args.__dict__
    for key in args_dict:
        if key in default_init_params:  # is an init param
            init_params[key] = args_dict[key]  # set initialisation parameters
        elif key in default_params:  # is a program param
            # set program/get_chat_messages parameters
            program_params[key] = args_dict[key]
        else:  # neither
            pass

    downloader = ChatDownloader(init_params)

    # TODO make command line args for these:
    other_params = {
        'indent': 4,  # '\t'
        'sort_keys': True,
        'overwrite': True,  # default to be False

        # if args.format set... add to params dict
        # 'format': 'something'  # TODO
    }

    # TODO DEBUGGING:
    program_params['testing'] = True
    # program_params['logging'] = 'none'

    if program_params['testing']:
        program_params['logging'] = 'debug'
        program_params['pause_on_debug'] = True
        program_params['message_groups'] = 'all'
        # program_params['timeout'] = 180

    if program_params['verbose']:
        program_params['logging'] = 'debug'

    if program_params['logging'] == 'none':
        get_logger().disabled = True
    else:
        set_log_level(program_params['logging'])

    output_file = None
    try:
        # TODO print program version
        log('debug', 'Python version: {}'.format(sys.version))

        chat = downloader.get_chat(program_params)

        log('debug', 'Chat information: {}'.format(chat.__dict__))

        if isinstance(program_params['max_messages'], int):
            chat.chat = itertools.islice(
                chat.chat, program_params['max_messages'])

        log('info', 'Retrieving chat for "{}".'.format(chat.title))

        format_file = program_params.get('format_file')

        formatter = ItemFormatter(format_file)
        format_name = program_params.get('format')

        if format_name is None:
            format_name = chat.site._DEFAULT_FORMAT or 'default'

        def print_formatted(item):
            if program_params['logging'] != 'none':
                formatted = formatter.format(item, format_name=format_name)
                safe_print(formatted)

        if program_params['output']:
            output_file = ContinuousWriter(
                program_params['output'], **other_params)

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
        NoContinuation,
        RetriesExceeded
    ) as e:
        log('error', e)
        # log('error', e, logging_level)  # always show
        # '{} ({})'.format(, e.__class__.__name__)

    except RequestException as e:
        log('error', 'Unable to establish a connection. Please check your internet connection. {}'.format(e))
        # log('error', e)  # traceback.format_exc()
        # TODO if e instance of (no internet connection)...
    except TimeoutException as e:
        log('info', e)

    except KeyboardInterrupt as e:
        log('error', 'Keyboard Interrupt')

    finally:
        if program_params['output'] and output_file:
            output_file.close()
