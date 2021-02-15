"""Console script for chat_downloader."""
import argparse
import re
from docstring_parser import parse as doc_parse


from .chat_downloader import (
    ChatDownloader,
    run
)

from .metadata import __version__

from .utils import (
    get_default_args,
    int_or_none
)


def main():

    parser = argparse.ArgumentParser(
        description='A simple tool used to retrieve chat messages from livestreams, videos, clips and past broadcasts. No authentication needed!',
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument('--version', action='version',
                        version=__version__)

    # PROGRAM PARAMS
    parser.add_argument(
        'url', help='The URL of the livestream, video, clip or past broadcast')

    def get_info(function):
        info = {}

        docstring = doc_parse(function.__doc__)
        args = get_default_args(function)

        for param in docstring.params:
            info[param.arg_name] = {
                'help': param.description,
                'default': args.get(param.arg_name)
            }
        return info

    # get help and default info
    get_chat_info = get_info(ChatDownloader.get_chat)
    get_init_info = get_info(ChatDownloader.__init__)

    def add_param(param_type, group, *keys, **kwargs):

        is_boolean_flag = kwargs.pop('is_boolean_flag', None)

        if is_boolean_flag:
            # If True by default, set action to store_false
            # If False by default, set action to store_false

            default = kwargs.pop('default', None)
            kwargs['action'] = 'store_{}'.format(
                str(not bool(default)).lower())

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
    output_group.add_argument('--indent', type=lambda x: int_or_none(x, x),
                              help='Number of spaces to indent JSON objects by. If nonnumerical input is provided, this will be used to indent the objects.', default=4)
    output_group.add_argument(
        '--overwrite', help='Overwrite output file if it exists. Otherwise, append to the end of the file.', action='store_true')

    debug_group = parser.add_argument_group('Debugging/Testing Arguments')

    on_debug_options = debug_group.add_mutually_exclusive_group()
    add_chat_param(on_debug_options, '--pause_on_debug', is_boolean_flag=True)
    add_chat_param(on_debug_options, '--exit_on_debug', is_boolean_flag=True)

    debug_options = debug_group.add_mutually_exclusive_group()
    add_chat_param(debug_options, '--logging',
                   choices=['none', 'debug', 'info', 'warning', 'error', 'critical'])

    debug_options.add_argument(
        '--testing', help='Enable testing mode. This is equivalent to setting logging to debug and enabling pause_on_debug', action='store_true')
    debug_options.add_argument(
        '--verbose', '-v', help='Print various debugging information. This is equivalent to setting logging to debug', action='store_true')
    debug_options.add_argument(
        '--quiet', '-q', help='Activate quiet mode (hide all output)', action='store_true')

    # INIT PARAMS
    init_group = parser.add_argument_group('Initialisation Arguments')
    add_init_param(init_group, '--cookies', '-c')
    add_init_param(init_group, '--proxy', '-p')

    # TODO add headers (user agent) as arg

    parser._positionals.title = 'Mandatory Arguments'
    parser._optionals.title = 'General Arguments'

    args = parser.parse_args()

    # Finished parsing CLI arguments
    # Run with these arguments
    run(**args.__dict__)
