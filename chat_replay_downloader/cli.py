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


from .sites.common import ChatDownloader
from .output.continuous_write import ContinuousWriter

from .utils import (
    update_dict_without_overwrite,
    multi_get,
    log,
    safe_print,
    set_log_level
)

from .formatting.format import ItemFormatter


def main():

    default_init_params = ChatDownloader._DEFAULT_INIT_PARAMS
    default_params = ChatDownloader._DEFAULT_PARAMS

    parser = argparse.ArgumentParser(
        description='A simple tool used to retrieve chat messages from streams, clips and past broadcasts. No authentication needed!',
        formatter_class=argparse.RawTextHelpFormatter)

    # PROGRAM PARAMS
    parser.add_argument('url', help='YouTube/Twitch video URL')

    parser.add_argument('--start_time', '-s', default=default_params['start_time'],
                        help='start time in seconds or hh:mm:ss\n(default: %(default)s)')
    parser.add_argument('--end_time', '-e', default=default_params['end_time'],
                        help='end time in seconds or hh:mm:ss\n(default: %(default)s = until the end)')

    parser.add_argument('--output', '-o', default=default_params['output'],
                        help='name of output file\n(default: %(default)s = print to standard output)')

    parser.add_argument('--pause_on_debug', default=default_params['pause_on_debug'],
                        help='whether to pause on certain debug messages.\n(default: %(default)s)')

    debug_group = parser.add_mutually_exclusive_group()

    debug_group.add_argument('--logging', choices=['none', 'debug', 'info', 'warning', 'error', 'critical'], default=default_params['logging'],
                             help='level of logging to show\n(default: %(default)s)')

    debug_group.add_argument('--testing', action='store_true', default=default_params['testing'],
                             help='print various debugging information\n(default: %(default)s)')

    # parser.add_argument('--safe_print', action='store_true', default=default_params['safe_print'],
    #                     help='level of logging to show\n(default: %(default)s)')

    parser.add_argument('--max_attempts', type=int, default=default_params['max_attempts'],
                        help='maximum number of attempts to retrieve chat messages. \n(default: %(default)s)')

    parser.add_argument('--retry_timeout', type=float, default=default_params['retry_timeout'],
                        help='number of seconds to wait before retrying. Setting this to a negative number will wait for user input.\n(default: %(default)s = use exponential backoff, i.e. immediate, 1s, 2s, 4s, 8s, ...)')

    parser.add_argument('--max_messages', type=int, default=default_params['max_messages'],
                        help='maximum number of messages to retrieve\n(default: %(default)s = unlimited)')

    parser.add_argument('--inactivity_timeout', type=float, default=default_params['inactivity_timeout'],
                        help='stop getting messages after not receiving anything for a certain duration (in seconds).\n(default: %(default)s)')

    parser.add_argument('--force_no_timeout', action='store_true', default=default_params['force_no_timeout'],
                        help='force no timeout between subsequent requests\n(default: %(default)s)')

    parser.add_argument('--timeout', type=float, default=default_params['timeout'],
                        help='stop retrieving chat after a certain duration (in seconds).\n(default: %(default)s = use exponential backoff, i.e. immediate, 1s, 2s, 4s, 8s, ...)')
    # TODO request_timeout
    # specify how long to spend on any single http request

    # TODO
    # parser.add_argument('--force_encoding', default=default_params['force_encoding'],
    #                     help='force certain encoding\n(default: %(default)s)')

    # Formatting
    parser.add_argument('--format', default=default_params['format'],
                        help='specify how messages should be formatted for printing\n(default: %(default)s = use site default)')
    parser.add_argument('--format_file', default=default_params['format_file'],
                        help='specify the format file to choose formats from\n(default: %(default)s)')

    # INIT PARAMS
    parser.add_argument('--cookies', '-c', default=default_init_params['cookies'],
                        help='name of cookies file\n(default: %(default)s)')

    def splitter(s):
        return [item.strip() for item in re.split('[\s,;]+', s)]

    # Specify message types/groups
    group = parser.add_mutually_exclusive_group()

    group.add_argument('--message_groups', type=splitter, default=default_params['message_groups'],
                       help='comma separated list of groups of messages to include\n(default: %(default)s)')

    group.add_argument('--message_types', type=splitter, default=default_params['message_types'],
                       help='comma separated list of types of messages to include\n(default: %(default)s)')

    parser.add_argument('--chat_type', choices=['live', 'top'], default=default_params['chat_type'],
                        help='which chat to get messages from [YouTube only]\n(default: %(default)s)')

    parser.add_argument('--message_receive_timeout', type=float, default=default_params['message_receive_timeout'],
                        help='time before requesting for new messages [Twitch only]\n(default: %(default)s)')

    parser.add_argument('--buffer_size', type=int, default=default_params['buffer_size'],
                        help='specify a buffer size for retrieving messages [Twitch only]\n(default: %(default)s)')

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

    downloader = ChatReplayDownloader(init_params)

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

    if program_params['testing']:
        program_params['logging'] = 'debug'
        program_params['pause_on_debug'] = True
        program_params['message_groups'] = 'all'
        # program_params['timeout'] = 180

    if program_params['logging'] != 'none':
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

    except (URLNotProvided, SiteNotSupported, LoginRequired, VideoUnavailable, NoChatReplay, VideoUnplayable, InvalidParameter, InvalidURL, NoContinuation) as e:
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
