from chat_replay_downloader import *
import os
import sys
import subprocess
import inspect


class HiddenPrints:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout


defaults = {
    'start_time': 0,
    'end_time': None,
    'message_type': 'messages',
    'chat_type': 'live'
}


def create_test(
    name, url,
    start_time=defaults['start_time'],
    end_time=defaults['end_time'],
    message_type=defaults['message_type'],
    chat_type=defaults['chat_type']
):

    data = locals()

    final = {key: value for (key, value) in data.items() if (
        key in defaults and data[key] != defaults[key])}
    data['args_info'] = final
    params = ["'{}'".format(data['url'])] + ['{}={}'.format(key, (value if (isinstance(value, int)
                                                                            or isinstance(value, float)) else "'{}'".format(value))) for (key, value) in final.items()]
    data['function_call'] = "get_chat_replay({})".format(', '.join(params))
    return data


youtube = [
    create_test(
        '[YouTube] Get live chat replay',
        'https://www.youtube.com/watch?v=wXspodtIxYU', end_time=100
    ),
    create_test(
        '[YouTube] Get live chat replay with start and end time',
        'https://www.youtube.com/watch?v=JIB3JbIIbPU', start_time=300, end_time=400
    ),
    create_test(
        '[YouTube] Get superchat messages from live chat replay',
        'https://www.youtube.com/watch?v=97w16cYskVI', end_time=100, message_type='superchat'
    ),
    create_test(
        '[YouTube] Get messages from live chat replay',
        'https://www.youtube.com/watch?v=wXspodtIxYU', start_time=100, end_time=200, message_type='all',
    ),
    create_test(
        '[YouTube] Get all types of messages from top chat replay',
        'https://www.youtube.com/watch?v=wXspodtIxYU', end_time=100, chat_type='top'
    ),
    create_test(
        '[YouTube] Get messages from premiered video',
        'https://www.youtube.com/watch?v=zVCs9Cug_qM'
    )
]


youtube_errors = [
    create_test(
        '[YouTube] Video does not exist',
        'https://www.youtube.com/watch?v=xxxxxxxxxxx'
    ),
    create_test(
        '[YouTube] Members-only content',
        'https://www.youtube.com/watch?v=vprErlL1w2E'
    ),
    create_test(  # May be time-specific
        '[YouTube] Chat is disabled for this live stream',
        'https://www.youtube.com/watch?v=XWq5kBlakcQ'
    ),
    create_test(
        '[YouTube] Live chat replay has been turned off for this video',
        'https://www.youtube.com/watch?v=7lGZvbasx6A'
    ),
    create_test(
        '[YouTube] Video is private',
        'https://www.youtube.com/watch?v=ijFMXqa-N0c'
    ),
    create_test(
        '[YouTube] Ending has strange times',
        'https://www.youtube.com/watch?v=DzEbfQI4TPQ', start_time='3:30:46'
    )
]

# random vod with chat replay (since most are deleted)
twitch_vod_url = 'https://www.twitch.tv/videos/449716115'

twitch = [
    create_test(
        '[Twitch] Get live chat replay',
        twitch_vod_url
    ),
    create_test(
        '[Twitch] Get live chat replay with start and end time',
        twitch_vod_url, start_time=300, end_time=3000
    )
]

twitch_errors = [
    create_test(
        '[Twitch] Video does not exist',
        'https://www.twitch.tv/videos/111111111'
    ),

    create_test(
        '[Twitch] Subscriber only',
        'https://www.twitch.tv/videos/123456789'
    ),
]


""" modes
True - Run all tests without documentation (run standard and errors)
False - Generate documentation only (do not run and do not include errors)
"""

modes = [True, False]

standard_tests = (youtube + twitch)
error_tests = (youtube_errors + twitch_errors)
for mode in modes:
    tests = standard_tests
    if (mode):
        tests += error_tests

    out_file = os.devnull if mode else 'EXAMPLES.md'
    example_file = open(out_file, 'w+', encoding='utf-8')

    print('## Examples', file=example_file)
    print('This file was automatically generated using `python run_tests.py`',
          file=example_file)

    counter = 1
    for test in tests:
        print('Running test {} on "{}" with params: start_time={}, end_time={}, message_type={}, chat_type={}.'.format(
            test['name'], test['url'], test['start_time'], test['end_time'], test['message_type'], test['chat_type']
        ))

        print('### {}. {}'.format(counter, test['name']), file=example_file)

        print('#### Python:', file=example_file)
        print('```python\n{}\n```\n'.format(
            test['function_call']), file=example_file)

        try:
            messages = []
            with HiddenPrints():
                if (mode):
                    messages = get_chat_replay(
                        test['url'],
                        start_time=test['start_time'],
                        end_time=test['end_time'],
                        message_type=test['message_type'],
                        chat_type=test['chat_type']
                    )

            print('Successfully retrieved {} messages.'.format(len(messages)))

        except InvalidURL as e:
            print('[Invalid URL]', e)
        except ParsingError as e:
            print('[Parsing Error] Unable to parse video data.', e)
        except NoChatReplay as e:
            print('[No Chat Replay]', e)
        except VideoUnavailable as e:
            print('[Video Unavailable]', e)
        except TwitchError as e:
            print('[Twitch Error]', e)
        except KeyboardInterrupt:
            print('Interrupted.')
        print()

        args = ['-{} {}'.format(key, ('"{}"'.format(value) if (' ' in str(value)) else value))
                for (key, value) in test['args_info'].items()]
        command = 'python chat_replay_downloader.py "{}" {}'.format(
            test['url'], ' '.join(args))
        print('#### Command line:', file=example_file)

        print('Print to standard output:', file=example_file)
        print('```\n{}\n```\n'.format(command), file=example_file)
        extensions = ['txt', 'csv', 'json']
        name_template = 'examples/'+test['name']+'.{}'

        for extension in extensions:

            name = name_template.format(extension)
            print('['+extension.upper()+' output](<'+name+'>)', file=example_file)

            new_command = '{} -output "{}"'.format(command, name)
            print('Running "{}"'.format(new_command))
            print('```\n{}\n```\n'.format(new_command), file=example_file)
            if (mode and test not in error_tests):
                subprocess.Popen(new_command).communicate()

        print('\n')
        counter += 1
