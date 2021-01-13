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
    safe_print
)

from .formatting.format import ItemFormatter

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

    debug_group = parser.add_mutually_exclusive_group()

    debug_group.add_argument('--logging', choices=['normal', 'none', 'errors', 'debug'], default=default_params['logging'],
                        help='level of logging to show\n(default: %(default)s)')
    debug_group.add_argument('--verbose', '-v', action='store_true', default=default_params['verbose'],
                        help='print various debugging information\n(default: %(default)s)')

    parser.add_argument('--safe_print', action='store_true', default=default_params['safe_print'],
                        help='level of logging to show\n(default: %(default)s)')
    parser.add_argument('--pause_on_debug', action='store_true', default=default_params['pause_on_debug'],
                        help='wait for user input after an error occurs\n(default: %(default)s)')

    parser.add_argument('--max_attempts', type=int, default=default_params['max_attempts'],
                        help='maximum number of attempts to retrieve chat messages. \n(default: %(default)s)')

    parser.add_argument('--retry_timeout', type=int, default=default_params['retry_timeout'],
                        help='number of seconds to wait before retrying. Setting this to -1 will wait for user input.\n(default: %(default)s)')

    parser.add_argument('--max_messages', type=int, default=default_params['max_messages'],
                        help='maximum number of messages to retrieve\n(default: %(default)s = unlimited)')

    parser.add_argument('--timeout', type=float, default=default_params['timeout'],
                        help='stop getting messages after not receiving anything for a certain amount of time\n(default: %(default)s)')

    parser.add_argument('--force_no_timeout', action='store_true', default=default_params['force_no_timeout'],
                        help='force no timeout between subsequent requests\n(default: %(default)s)')

    # TODO
    # parser.add_argument('--force_encoding', default=default_params['force_encoding'],
    #                     help='force certain encoding\n(default: %(default)s)')


    # formatting:
    parser.add_argument('--format', default=default_params['format'],
                        help='specify how messages should be formatted for printing\n(default: %(default)s)')
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

    # if program_params.get('logging') == 'none':
    #     f = open(os.devnull, 'w', encoding='utf-8')
    #     sys.stdout = f
    #     sys.stderr = f
    # else:
    #     # set encoding of standard output and standard error
    #     sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    #     sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

    downloader = ChatReplayDownloader(init_params)

    # printer = safeprint.Printer()

    # set PYTHONIOENCODING=utf-8
    # sys.setdefaultencoding('utf-8')

    # python -m chat_replay_downloader https://www.youtube.com/watch?v=nlGllxnSfgA --output test.json --start_time 5:32 --end_time 5:40
    # print(sys.getdefaultencoding())

    logging_level = program_params.get('logging')
    format_name = program_params.get('format')
    video_is_live = False
    def test_callback(item):
        if logging_level != 'none':
            formatted = formatter.format(item, format_name=format_name)
            safe_print(formatted)

            # try:
            #     # time = multi_get(item, 'timestamp') if video_is_live else multi_get(item, 'time_text')
            #     # author = multi_get(item, 'author', 'display_name') or multi_get(item, 'author', 'name')
            #     # message = (multi_get(item, 'message') or '').strip()
            #     # amount = multi_get(item, 'amount')

            #     # formatted = '[{}] {}{}: {}'.format(
            #     #     time,
            #     #     '*{}* '.format(amount) if amount else '',
            #     #     author,
            #     #     message
            #     # )

            #     # formatted = formatter.format(item, format_name='24_hour')
            #     # safe_print(item)

            #     # print(author,':', message.encode(encoding, 'ignore').decode(encoding, 'ignore'))
            #     #.encode(encoding).decode(encoding)
            #     # print(sys.getdefaultencoding())
            #     # printer.print(message)
            #     # print()#.encode('utf-8')
            #     # print(message.decode('utf-8'))
            #     # print(message.encode('utf-16'))
            # except OSError as e:
            #     print('PRINTING ERROR OCCURRED')
            #     print('Cause of error:')
            #     print(json.dumps(formatted))
            #     raise e
                # traceback.print_exc()
                # exit()



        # return  # TODO temporary - testing
        # #formatted = formatter.format(item, format_name='default')#
        # # print(item)
        # if formatted:
        #     if program_params.get('logging') in ('debug', 'normal'):
        #         if program_params.get('safe_print'):
        #             safe_print_text(formatted)
        #         else:
        #             print(formatted, flush=True)
        # else:
        #     # False and
        #     if program_params.get('logging') in ('debug', 'errors'):
        #         print('No format specified for type: ',
        #               item.get('message_type'))
        #         print(item)

    # TODO make command line args for these:
    other_params = {
        'indent': 4,  # '\t'
        'sort_keys': True,
        'overwrite': True,  # default to be False

        # if args.format set... add to params dict
        'format': 'something'  # TODO
    }
    formatter = ItemFormatter()

    callback = None  # test_callback

    if args.output:
        output_file = ContinuousWriter(args.output, **other_params)

        def write_to_file(item):
            test_callback(item)

            output_file.write(item, flush=True)

        callback = write_to_file
    else:
        callback = test_callback

    #program_params['callback'] = callback

    # TODO DEBUGGING:
    # Temporary
    program_params['pause_on_debug'] = True
    program_params['logging'] = 'errors'
    program_params['verbose'] = True
    program_params['message_groups'] = 'all'

    # program_params['retry_timeout'] = -1
    try:

        # TODO print program version
        log(
            'debug',
            'Python version: {}'.format(sys.version),
            program_params['logging'],
        )

        chat = downloader.get_chat(program_params)

        video_is_live = chat.is_live
        # print(messages)
        # print(messages.duration)
        # print(messages.chat)

        if isinstance(program_params['max_messages'], int):
            chat.chat = itertools.islice(
                chat.chat, program_params['max_messages'])



        # log the title
        log(
            'info',
            'Retrieving chat for "{}".'.format(chat.title),
            program_params['logging']
        )

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
        log('error', e, program_params['logging']) # always show

    # ParsingError,
    except RequestException as e:
        # TODO if e instance of (no internet connection)...
        log('error',
            'Unable to establish a connection. Please check your internet connection.',
            program_params['logging']
            )
        log(
            'error',
            [
                e,
                traceback.format_exc()
            ],
            program_params['logging'],
            matching=('debug', 'errors'),
            pause_on_debug=program_params['pause_on_debug']
        )
    except PermissionError as e:
        print('PermissionError', e)
    except KeyboardInterrupt:
        print('keyboard interrupt')

    except Exception as e:
        raise e
        print('unknown exception', type(e))
        print(e)
        traceback.print_exc()

    finally:
        if args.output:
            output_file.close()
