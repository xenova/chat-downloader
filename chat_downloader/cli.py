"""Console script for chat_downloader."""
import argparse
import re
from docstring_parser import parse as doc_parse


from .chat_downloader import (
    ChatDownloader,
    run
)

from .metadata import (
    __version__,
    __summary__,
    __program__
)

from .utils.core import (
    get_default_args,
    int_or_none
)

from .debugging import (
    disable_logger,
    set_log_level
)


def splitter(s):
    return [item.strip() for item in re.split(r'[\s,;]+', s)]


def str2bool(value):
    if isinstance(value, bool):
        return value
    value = value.lower()
    if value in ('true', 'yes',  't', 'y', '1', 'enable'):
        return True
    elif value in ('false', 'no', 'f', 'n', '0', 'disable'):
        return False
    else:
        raise argparse.ArgumentTypeError(
            f'Boolean value expected: {value} is not a boolean')


def main(cli_args=None):

    parser = argparse.ArgumentParser(
        description=__summary__,
        # formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.prog = __program__

    parser.add_argument('--version', action='version', version=__version__)

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
        info = get_chat_info if param_type == 'chat' else get_init_info
        key = keys[0].lstrip('-')
        group.add_argument(*keys, **info[key], **kwargs)

    def add_chat_param(group, *keys, **kwargs):
        add_param('chat', group, *keys, **kwargs)

    def add_init_param(group, *keys, **kwargs):
        add_param('init', group, *keys, **kwargs)

    add_chat_param(parser, 'url')

    time_group = parser.add_argument_group('Timing Arguments')

    add_chat_param(time_group, '--start_time', '-s')
    add_chat_param(time_group, '--end_time', '-e')

    # Specify message types/groups
    type_group = parser.add_argument_group('Message Type Arguments')
    type_options = type_group.add_mutually_exclusive_group()

    add_chat_param(type_options, '--message_types', type=splitter)
    add_chat_param(type_options, '--message_groups', type=splitter)

    retry_group = parser.add_argument_group(
        'Retry Arguments')  # what to do when an error occurs
    add_chat_param(retry_group, '--max_attempts', type=int)
    add_chat_param(retry_group, '--retry_timeout', type=float)
    add_chat_param(retry_group, '--interruptible_retry',
                   type=str2bool, nargs='?', const=True)

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
    # format_group.add_argument('--print_json', action='store_true', help='Print out json ', default=None)
    add_chat_param(format_group, '--format')
    add_chat_param(format_group, '--format_file')

    # info = get_site_info(YouTubeChatDownloader)
    youtube_group = parser.add_argument_group(
        '[Site Specific] YouTube Arguments')
    add_chat_param(youtube_group, '--chat_type',
                   choices=['live', 'top'])
    add_chat_param(youtube_group, '--ignore', type=splitter)
    # add_chat_param(
    #     youtube_group, '--force_no_timeout', action='store_true')

    # info = get_site_info(TwitchChatDownloader)
    twitch_group = parser.add_argument_group(
        '[Site Specific] Twitch Arguments')
    add_chat_param(
        twitch_group, '--message_receive_timeout', type=float)
    add_chat_param(twitch_group, '--buffer_size', type=int)

    output_group = parser.add_argument_group('Output Arguments')
    add_chat_param(output_group, '--output', '-o')
    add_chat_param(output_group, '--overwrite',
                   type=str2bool, nargs='?', const=True)
    add_chat_param(output_group, '--sort_keys',
                   type=str2bool, nargs='?', const=True)
    add_chat_param(output_group, '--indent', type=lambda x: int_or_none(x, x))

    # Debugging only available from the CLI
    debug_group = parser.add_argument_group('Debugging/Testing Arguments')

    on_debug_options = debug_group.add_mutually_exclusive_group()
    on_debug_options.add_argument('--pause_on_debug', action='store_true',
                                  help='Pause on certain debug messages, defaults to False')
    on_debug_options.add_argument('--exit_on_debug', action='store_true',
                                  help='Exit when something unexpected happens, defaults to False')

    debug_options = debug_group.add_mutually_exclusive_group()
    debug_options.add_argument('--logging', choices=['none', 'debug', 'info', 'warning', 'error', 'critical'],
                               help='Level of logging to display, defaults to info', default='info')

    debug_options.add_argument('--testing', action='store_true',
                               help='Enable testing mode. This is equivalent to setting logging to debug and enabling pause_on_debug. Defaults to False')
    debug_options.add_argument('--verbose', '-v', action='store_true',
                               help='Print various debugging information. This is equivalent to setting logging to debug. Defaults to False')
    debug_options.add_argument('--quiet', '-q', action='store_true',
                               help='Activate quiet mode (hide all output), defaults to False')

    # INIT PARAMS
    init_group = parser.add_argument_group('Initialisation Arguments')
    add_init_param(init_group, '--cookies', '-c')
    add_init_param(init_group, '--proxy', '-p')

    # TODO add headers (user agent) as arg

    parser._positionals.title = 'Mandatory Arguments'
    parser._optionals.title = 'General Arguments'

    args = parser.parse_args(args=cli_args)

    # Modify debugging args:
    if args.testing:  # (only for CLI)
        args.logging = 'debug'
        args.pause_on_debug = True

    if args.verbose:
        args.logging = 'debug'

    if args.quiet or args.logging == 'none':
        disable_logger()
    else:
        set_log_level(args.logging)

    # Run with these arguments
    run(**args.__dict__)
