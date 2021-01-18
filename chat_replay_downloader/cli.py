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

# import logging


# logging.NOTSET

#from .chat_replay_downloader import char

# import safeprint


def main():
    """Console script for chat_replay_downloader."""

    default_init_params = ChatDownloader._DEFAULT_INIT_PARAMS
    default_params = ChatDownloader._DEFAULT_PARAMS

    parser = argparse.ArgumentParser(
        description='A simple tool used to retrieve YouTube/Twitch chat from past broadcasts/VODs. No authentication needed!',
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

    debug_group.add_argument('--verbose', '-v', action='store_true', default=default_params['verbose'],
                             help='print various debugging information\n(default: %(default)s)')



    parser.add_argument('--safe_print', action='store_true', default=default_params['safe_print'],
                        help='level of logging to show\n(default: %(default)s)')

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

    # formatting:
    parser.add_argument('--format', default=default_params['format'],
                        help='specify how messages should be formatted for printing\n(default: %(default)s = use site default)')
    parser.add_argument('--format_file', default=default_params['format_file'],
                        help='specify the format file to choose formats from\n(default: %(default)s)')

    # INIT PARAMS
    parser.add_argument('--cookies', '-c', default=default_init_params['cookies'],
                        help='name of cookies file\n(default: %(default)s)')

    # TODO
    # add --calculate_start_time as a tag?

    # Additional params [Site Specific]

# choices=['messages', 'superchat', 'all']
# TODO message groups and message types?
    def splitter(s):
        return [item.strip() for item in re.split('[\s,;]+', s)]
    # joiner = lambda s: str(s)[1:-1] if isinstance(s, (list,tuple)) else s
    #', '.join(s) if s else s

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

    # print(args.message_type)
    # exit()
    # TODO temp:
    #args.logging = 'debug'

    # def print_error(message):
    #     print(message)
    #     if(args.logging in ('debug', '')):

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

# def run_main(init_params, program_params):

    # if program_params.get('logging') == 'none':
        # f = open(os.devnull, 'w', encoding='utf-8')
        # sys.stdout = f
        # sys.stderr = f
    # else:
    #     # set encoding of standard output and standard error
    #     sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    #     sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

    downloader = ChatReplayDownloader(init_params)


    video_is_live = False

    # TODO make command line args for these:
    other_params = {
        'indent': 4,  # '\t'
        'sort_keys': True,
        'overwrite': True,  # default to be False

        # if args.format set... add to params dict
        # 'format': 'something'  # TODO
    }

    # TODO DEBUGGING:
    # Temporary
    program_params['verbose'] = True
    program_params['pause_on_debug'] = True
    program_params['message_groups'] = 'all'
    program_params['timeout'] = 120
    # program_params['inactivity_timeout'] = 20
    # program_params['retry_timeout'] = 5
    # program_params['logging'] = 'debug'  # 'debug', 'info'



    if program_params['verbose']:
        program_params['logging'] = 'debug'

    if program_params['logging'] != 'none':
        set_log_level(program_params['logging'])
    else:
        pass
        # set_log_level('notset')
    #     f = open(os.devnull, 'w', encoding='utf-8')
    #     sys.stdout = f
    #     sys.stderr = f
    # else:
    #     set_log_level(program_params['logging'])
    # program_params['retry_timeout'] = -1

    try:
        # TODO print program version
        log('debug', 'Python version: {}'.format(sys.version))

        chat = downloader.get_chat(program_params)

        video_is_live = chat.is_live

        # print(messages)
        # print(messages.duration)
        # print(messages.chat)

        if isinstance(program_params['max_messages'], int):
            chat.chat = itertools.islice(
                chat.chat, program_params['max_messages'])

        # log the title
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
            output_file = ContinuousWriter(program_params['output'], **other_params)

            def write_to_file(item):
                print_formatted(item)
                output_file.write(item, flush=True)

            callback = write_to_file
        else:
            callback = print_formatted

        # message_count = 0
        #     message_count+=1
        for message in chat:
            callback(message)

            # log(
            #     'debug',
            #     'Total number of messages: {}'.format(message_count),
            #     program_params['logging'],
            #     matching=('debug', 'errors')
            # )

            # percentage = round(100*message.get('time_in_seconds')/chat.duration, 2)
            # print(percentage, end='\r')

        # for i in messages:
        #     print(i, flush=True)
        #     time.sleep(1)
        # messages = downloader.get_chat_messages(program_params)

        # log(
        #     'debug',
        #     'Finished retrieving chat replay.',
        #     program_params['logging'],
        #     matching=('debug', 'errors')
        # )

    except (LoginRequired, VideoUnavailable, NoChatReplay, VideoUnplayable, InvalidParameter, InvalidURL, NoContinuation) as e:
        log('error', e)
        # log('error', e, logging_level)  # always show
        # '{} ({})'.format(, e.__class__.__name__)

    except RequestException as e:
        log('error', 'Unable to establish a connection. Please check your internet connection.')
        log('error', e)  # traceback.format_exc()
        # TODO if e instance of (no internet connection)...
    except TimeoutException as e:
        log('info', e)

    except PermissionError as e:
        print('PermissionError', e)
        raise e
    except KeyboardInterrupt:
        print('keyboard interrupt')

    except Exception as e:
        print('unknown exception', type(e))
        print(e)
        traceback.print_exc()
        raise e

    finally:
        if program_params['output']:
            output_file.close()
