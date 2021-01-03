"""Console script for chat_replay_downloader."""
import argparse
import sys
import os
import codecs
import json
import traceback
import itertools
from requests.exceptions import RequestException

from .chat_replay_downloader import *

from .sites.common import ChatDownloader
from .output.continuous_write import ContinuousWriter

from .utils import (
    update_dict_without_overwrite,
    safe_print_text,
    multi_get,
    log
)

from .formatting.format import ItemFormatter

# from .errors import (
#     LoadError
# )

#from .chat_replay_downloader import char


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

    parser.add_argument('--logging', choices=['normal', 'none', 'errors', 'debug'], default=default_params['logging'],
                        help='level of logging to show\n(default: %(default)s)')

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

    if program_params.get('logging') == 'none':
        f = open(os.devnull, 'w', encoding='utf-8')
        sys.stdout = f
        sys.stderr = f
    else:
        # set encoding of standard output and standard error
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

    downloader = ChatReplayDownloader(init_params)

    def test_callback(item):
        formatted = '[{}] {}: {}'.format(
            multi_get(item, 'timestamp') or multi_get(item, 'time_text'),
            multi_get(item, 'author', 'name'),
            multi_get(item, 'message')
        )
        if program_params.get('logging') != 'none':
            safe_print_text(formatted)
        return  # TODO temporary - testing
        #formatted = formatter.format(item, format_name='default')#
        # print(item)
        if formatted:
            if program_params.get('logging') in ('debug', 'normal'):
                if program_params.get('safe_print'):
                    safe_print_text(formatted)
                else:
                    print(formatted, flush=True)
        else:
            # False and
            if program_params.get('logging') in ('debug', 'errors'):
                print('No format specified for type: ',
                      item.get('message_type'))
                print(item)

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

            output_file.write(item)

        callback = write_to_file
    else:
        callback = test_callback

    #program_params['callback'] = callback

    # TODO DEBUGGING:
    # Temporary
    # program_params['pause_on_debug'] = True
    program_params['logging'] = 'errors'
    program_params['message_groups'] = 'all'

    # program_params['retry_timeout'] = -1
    try:
        messages = downloader.get_chat_messages(program_params)

        if isinstance(program_params['max_messages'], int):
            messages = itertools.islice(
                messages, program_params['max_messages'])

        for message in messages:
            callback(message)
        log(
            'debug',
            'Finished retrieving chat replay.',
            program_params['logging'],
            matching=('debug', 'errors')
        )

    except (LoginRequired, VideoUnavailable, NoChatReplay, VideoUnplayable) as e:
        log('error', e, program_params['logging'])

    # ParsingError,
    except RequestException as e:
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
        print('unknown exception', type(e))
        print(e)
        traceback.print_exc()

    finally:
        if args.output:
            output_file.close()

    # except Exception as e:
    #     print('other exception')
    #     print(e)
    #     pass

    #
    # print('got',len(program_params.get('messages')),'messages')

    # #print(program_params.get('messages'))
    # with open('test.json', 'w') as outfile:
    #     json.dump(program_params.get('messages'), outfile, indent=4, sort_keys=True)

    #print(json.dumps(options.get('messages'), indent=4))

    #z = a.get('messages')

    # print(q)
    # print('got',len(z),'messages')

#     return


#     try:
#         chat_downloader = ChatReplayDownloader(cookies=args.cookies)

#         num_of_messages = 0

#         def print_item(item):
#             chat_downloader.print_item(item)

#         def write_to_file(item):

#             # only file format capable of appending properly
#             with open(args.output, 'a', encoding='utf-8') as f:
#                 if('ticker_duration' not in item):  # needed for duplicates
#                     num_of_messages += 1
#                     print_item(item)
#                     text = chat_downloader.message_to_string(item)
#                     print(text, file=f)

#         callback = None if args.output is None else print_item
#         if(args.output is not None):
#             if(args.output.endswith('.json')):
#                 pass
#             elif(args.output.endswith('.csv')):
#                 fieldnames = []
#             else:
#                 open(args.output, 'w').close()  # empty the file
#                 callback = write_to_file

#         chat_messages = chat_downloader.get_chat_replay(
#             args.url,
#             start_time=args.start_time,
#             end_time=args.end_time,
#             message_types=args.message_types,
#             chat_type=args.chat_type,
#             callback=callback
#         )

#         if(args.output is not None):
#             if(args.output.endswith('.json')):
#                 num_of_messages = len(chat_messages)
#                 with open(args.output, 'w') as f:
#                     json.dump(chat_messages, f, sort_keys=True)

#             elif(args.output.endswith('.csv')):
#                 num_of_messages = len(chat_messages)
#                 fieldnames = []
#                 for message in chat_messages:
#                     fieldnames = list(set(fieldnames + list(message.keys())))
#                 fieldnames.sort()

#                 with open(args.output, 'w', newline='', encoding='utf-8') as f:
#                     fc = csv.DictWriter(f, fieldnames=fieldnames)
#                     fc.writeheader()
#                     fc.writerows(chat_messages)

#             print('Finished writing', num_of_messages,
#                   'messages to', args.output, flush=True)

#     except InvalidURL as e:
#         print('[Invalid URL]', e)
#     except ParsingError as e:
#         print('[Parsing Error]', e)
#     except NoChatReplay as e:
#         print('[No Chat Replay]', e)
#     except VideoUnavailable as e:
#         print('[Video Unavailable]', e)
#     except TwitchError as e:
#         print('[Twitch Error]', e)
#     except (LoadError, CookieError) as e:
#         print('[Cookies Error]', e)
#     except KeyboardInterrupt:
#         print('Interrupted.')
#     return 0


# if __name__ == "__main__":
#     sys.exit(main())  # pragma: no cover
