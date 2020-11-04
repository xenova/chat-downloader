from chat_replay_downloader import *
import os
import sys
import subprocess
import inspect


def do_nothing(item):
    pass


command_line_arguments = [
    'start_time',
    'end_time',
    'message_type',
    'chat_type',
    'output',
    'cookies'
]

defaults = {
    'start_time': 0,
    'end_time': None,
    'message_type': 'messages',
    'chat_type': 'live',
    'output': None,
    'callback': None
}


def create_test(
    name, url,
    start_time=defaults['start_time'],
    end_time=defaults['end_time'],
    message_type=defaults['message_type'],
    chat_type=defaults['chat_type'],
    callback=defaults['callback']
):

    data = locals()

    final = {key: value for (key, value) in data.items() if (
        key in defaults and key in command_line_arguments and data[key] != defaults[key])}

    params = ["'{}'".format(data['url'])] + ['{}={}'.format(key, (value if (isinstance(value, int)
                                                                            or isinstance(value, float)) else "'{}'".format(value))) for (key, value) in final.items()]
    data['function_call'] = "messages = get_chat_replay({})".format(
        ', '.join(params))

    args = ['-{} {}'.format(key, ('"{}"'.format(value) if (' ' in str(value)) else value))
            for (key, value) in final.items()]

    data['command'] = 'python chat_replay_downloader.py "{}"{}{}'.format(
        url, '' if len(args) == 0 else ' ', ' '.join(args))
    return data


youtube = [
    create_test(
        '[YouTube] Get live chat replay',
        'https://www.youtube.com/watch?v=wXspodtIxYU', end_time=100, callback=do_nothing
    ),
    create_test(
        '[YouTube] Get live chat replay with start and end time',
        'https://www.youtube.com/watch?v=JIB3JbIIbPU', start_time=300, end_time=400, callback=do_nothing
    ),
    create_test(
        '[YouTube] Get superchat messages from live chat replay',
        'https://www.youtube.com/watch?v=97w16cYskVI', end_time=100, message_type='superchat', callback=do_nothing
    ),
    create_test(
        '[YouTube] Get messages from live chat replay',
        'https://www.youtube.com/watch?v=wXspodtIxYU', start_time=100, end_time=200, message_type='all', callback=do_nothing
    ),
    create_test(
        '[YouTube] Get all types of messages from top chat replay',
        'https://www.youtube.com/watch?v=wXspodtIxYU', end_time=100, chat_type='top', callback=do_nothing
    ),
    create_test(
        '[YouTube] Get messages from premiered video',
        'https://www.youtube.com/watch?v=zVCs9Cug_qM', callback=do_nothing
    )
]

youtube_errors = [
    create_test(
        '[YouTube] Video does not exist',
        'https://www.youtube.com/watch?v=xxxxxxxxxxx', callback=do_nothing
    ),
    create_test(
        '[YouTube] Members-only content',
        'https://www.youtube.com/watch?v=vprErlL1w2E', callback=do_nothing
    ),
    create_test(  # May be time-specific
        '[YouTube] Chat is disabled for this live stream',
        'https://www.youtube.com/watch?v=XWq5kBlakcQ', callback=do_nothing
    ),
    create_test(
        '[YouTube] Live chat replay has been turned off for this video',
        'https://www.youtube.com/watch?v=7lGZvbasx6A', callback=do_nothing
    ),
    create_test(
        '[YouTube] Video is private',
        'https://www.youtube.com/watch?v=ijFMXqa-N0c', callback=do_nothing
    ),
    create_test(
        '[YouTube] Ending has strange times',
        'https://www.youtube.com/watch?v=DzEbfQI4TPQ', start_time='3:30:46', callback=do_nothing
    ),
    create_test(
        '[YouTube] Messages that cause OSErrors',
        'https://www.youtube.com/watch?v=Aymrnzianf0', start_time='24:00', end_time='25:00', callback=do_nothing
    )
]

# random vod with chat replay (since most are deleted)
twitch_vod_url = 'https://www.twitch.tv/videos/449716115'

twitch = [
    create_test(
        '[Twitch] Get live chat replay',
        twitch_vod_url, callback=do_nothing
    ),
    create_test(
        '[Twitch] Get live chat replay with start and end time',
        twitch_vod_url, start_time=300, end_time=3000, callback=do_nothing
    )
]

twitch_errors = [
    create_test(
        '[Twitch] Video does not exist',
        'https://www.twitch.tv/videos/111111111', callback=do_nothing
    ),

    create_test(
        '[Twitch] Subscriber only',
        'https://www.twitch.tv/videos/123456789', callback=do_nothing
    ),
]

### CONTROLS ###
run = True
document = True


standard_tests = (youtube + twitch)
error_tests = (youtube_errors + twitch_errors)

all_tests = standard_tests + error_tests

extensions = ['txt', 'csv', 'json']


def print_test(test):
    global counter
    print('({}) {:=^120}'.format(counter, ' '+test['name']+' '))


if run:
    counter = 1

    print('Begin running tests.')

    for test in all_tests:
        print_test(test)
        try:
            print('Running', '"{}"'.format(test['function_call']))
            messages = get_chat_replay(
                test['url'],
                start_time=test['start_time'],
                end_time=test['end_time'],
                message_type=test['message_type'],
                chat_type=test['chat_type'],
                callback=test['callback']
            )
        except InvalidURL as e:
            print('[Invalid URL]', e)
        except ParsingError as e:
            print('[Parsing Error]', e)
        except NoChatReplay as e:
            print('[No Chat Replay]', e)
        except VideoUnavailable as e:
            print('[Video Unavailable]', e)
        except TwitchError as e:
            print('[Twitch Error]', e)
        except (LoadError, CookieError) as e:
            print('[Cookies Error]', e)
        except KeyboardInterrupt:
            print('Interrupted.')

        name_template = 'examples/'+test['name']+'.{}'
        for extension in extensions:
            name = name_template.format(extension)
            new_command = '{} -output "{}"'.format(test['command'], name)
            print('Running "{}"'.format(new_command))
            if(test not in error_tests):
                subprocess.Popen(
                    '{} --hide_output'.format(new_command)).communicate()
        counter += 1
        print()

if document:
    counter = 1

    print('Begin documenting standard tests.')

    example_file = open('EXAMPLES.md', 'w+', encoding='utf-8')

    print('## Examples', file=example_file)
    print('This file was automatically generated using `python run_tests.py`',
          file=example_file)

    for test in standard_tests:
        print_test(test)
        print('### {}. {}'.format(counter, test['name']), file=example_file)
        print('#### Python:', file=example_file)
        print('```python\n{}\n```\n'.format(
            test['function_call']), file=example_file)

        print('#### Command line:', file=example_file)
        print('Print to standard output:', file=example_file)
        print('```\n{}\n```\n'.format(test['command']), file=example_file)

        name_template = 'examples/'+test['name']+'.{}'
        for extension in extensions:
            name = name_template.format(extension)
            print('['+extension.upper()+' output](<'+name+'>)', file=example_file)

            new_command = '{} -output "{}"'.format(test['command'], name)
            print('```\n{}\n```\n'.format(new_command), file=example_file)
        counter += 1
        print()

    example_file.close()
