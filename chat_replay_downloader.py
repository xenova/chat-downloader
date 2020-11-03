#!/usr/bin/env python3
import requests
import json
import datetime
import re
import argparse
import bs4
import csv
import emoji
import time
import os
from http.cookiejar import MozillaCookieJar, LoadError


class CallbackFunction(Exception):
    """Raised when the callback function does not have (only) one required positional argument"""
    pass


class VideoNotFound(Exception):
    """Raised when video cannot be found."""
    pass


class ParsingError(Exception):
    """Raised when video data cannot be parsed."""
    pass


class VideoUnavailable(Exception):
    """Raised when video is unavailable (e.g. if video is private)."""
    pass


class NoChatReplay(Exception):
    """Raised when the video does not contain a chat replay."""
    pass


class InvalidURL(Exception):
    """Raised when the url given is invalid (neither YouTube nor Twitch)."""
    pass


class TwitchError(Exception):
    """Raised when an error occurs with a Twitch video."""
    pass


class NoContinuation(Exception):
    """Raised when there are no more messages to retrieve (in a live stream)."""
    pass


class CookieError(Exception):
    """Raised when an error occurs while loading a cookie file."""
    pass


class ChatReplayDownloader:
    """A simple tool used to retrieve YouTube/Twitch chat from past broadcasts/VODs. No authentication needed!"""

    __HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36',
        'Accept-Language': 'en-US, en'
    }

    __YT_REGEX = r'(?:/|%3D|v=|vi=)([0-9A-z-_]{11})(?:[%#?&]|$)'
    __YOUTUBE_API_BASE_TEMPLATE = 'https://www.youtube.com/{}/{}?continuation={}&pbj=1&hidden=false'
    __YOUTUBE_API_PARAMETERS_TEMPLATE = '&playerOffsetMs={}'

    __TWITCH_REGEX = r'(?:/videos/|/v/)(\d+)'
    __TWITCH_CLIENT_ID = 'kimne78kx3ncx6brgo4mv6wki5h1ko'  # public client id
    __TWITCH_API_TEMPLATE = 'https://api.twitch.tv/v5/videos/{}/comments?client_id={}'

    __TYPES_OF_MESSAGES = {
        'ignore': [
            # message saying Live Chat replay is on
            'liveChatViewerEngagementMessageRenderer',
            'liveChatPurchasedProductMessageRenderer',  # product purchased
            'liveChatPlaceholderItemRenderer',  # placeholder
            'liveChatModeChangeMessageRenderer'  # e.g. slow mode enabled
        ],
        'message': [
            'liveChatTextMessageRenderer'  # normal message
        ],
        'superchat_message': [  # superchat messages which appear in chat
            'liveChatMembershipItemRenderer',
            'liveChatPaidMessageRenderer',
            'liveChatPaidStickerRenderer'
        ],
        'superchat_ticker': [  # superchat messages which appear ticker (at the top)
            'liveChatTickerPaidStickerItemRenderer',
            'liveChatTickerPaidMessageItemRenderer',
            'liveChatTickerSponsorItemRenderer',
        ]
    }

    # used for debugging
    __TYPES_OF_KNOWN_MESSAGES = []
    for key in __TYPES_OF_MESSAGES:
        __TYPES_OF_KNOWN_MESSAGES.extend(__TYPES_OF_MESSAGES[key])

    __IMPORTANT_KEYS_AND_REMAPPINGS = {
        'timestampUsec': 'timestamp',
        'authorExternalChannelId': 'author_id',
        'authorName': 'author',
        'purchaseAmountText': 'amount',
        'message': 'message',
        'headerBackgroundColor': 'header_color',
        'bodyBackgroundColor': 'body_color',
        'timestampText': 'time_text',
        'amount': 'amount',
        'startBackgroundColor': 'body_color',
        'durationSec': 'ticker_duration',
        'detailText': 'message',
        'headerSubtext': 'message',  # equivalent to message - get runs
        'backgroundColor': 'body_color'
    }

    def __init__(self, cookies=None):
        """Initialise a new session for making requests."""
        self.session = requests.Session()
        self.session.headers = self.__HEADERS

        cj = MozillaCookieJar(cookies)
        if cookies is not None:
            # Only attempt to load if the cookie file exists.
            if os.path.exists(cookies):
                cj.load(ignore_discard=True, ignore_expires=True)
            else:
                raise CookieError(
                    "The file '{}' could not be found.".format(cookies))
        self.session.cookies = cj

    def __session_get(self, url):
        """Make a request using the current session."""
        return self.session.get(url)

    def __session_get_json(self, url):
        """Make a request using the current session and get json data."""
        return self.__session_get(url).json()

    def __timestamp_to_microseconds(self, timestamp):
        """
        Convert RFC3339 timestamp to microseconds.
        This is needed as datetime.datetime.strptime() does not support nanosecond precision.
        """
        info = list(filter(None, re.split('[\.|Z]{1}', timestamp))) + [0]
        return round((datetime.datetime.strptime('{}Z'.format(info[0]), '%Y-%m-%dT%H:%M:%SZ').timestamp() + float('0.{}'.format(info[1])))*1e6)

    def __time_to_seconds(self, time):
        """Convert timestamp string of the form 'hh:mm:ss' to seconds."""
        return sum(abs(int(x)) * 60 ** i for i, x in enumerate(reversed(time.replace(',', '').split(':')))) * (-1 if time[0] == '-' else 1)

    def __seconds_to_time(self, seconds):
        """Convert seconds to timestamp."""
        return re.sub(r'^0:0?', '', str(datetime.timedelta(0, seconds)))

    def __microseconds_to_timestamp(self, microseconds):
        """Convert unix time to human-readable timestamp."""
        return datetime.datetime.fromtimestamp(microseconds//1000000).strftime('%Y-%m-%d %H:%M:%S')

    def __arbg_int_to_rgba(self, argb_int):
        """Convert ARGB integer to RGBA array."""
        red = (argb_int >> 16) & 255
        green = (argb_int >> 8) & 255
        blue = argb_int & 255
        alpha = (argb_int >> 24) & 255
        return [red, green, blue, alpha]

    def __rgba_to_hex(self, colours):
        """Convert RGBA array to hex colour."""
        return '#{:02x}{:02x}{:02x}{:02x}'.format(*colours)

    def __get_colours(self, argb_int):
        """Given an ARGB integer, return both RGBA and hex values."""
        rgba_colour = self.__arbg_int_to_rgba(argb_int)
        hex_colour = self.__rgba_to_hex(rgba_colour)
        return {
            'rgba': rgba_colour,
            'hex': hex_colour
        }

    def message_to_string(self, item):
        """Format item for printing to standard output."""
        return '[{}] {}{}: {}'.format(
            item['time_text'] if 'time_text' in item else (
                self.__microseconds_to_timestamp(item['timestamp']) if 'timestamp' in item else ''),
            '*{}* '.format(item['amount']) if 'amount' in item else '',
            item['author'],
            item['message'] or ''
        )

    def print_item(self, item):
        """
        Ensure printing to standard output can be done safely (especially on Windows).
        There are usually issues with printing emojis and non utf-8 characters.
        """
        message = self.message_to_string(item)
        safe_string = emoji.demojize(message).encode(
            'utf-8').decode('utf-8', 'ignore')
        print(safe_string)

    def __parse_message_runs(self, runs):
        """ Reads and parses YouTube formatted messages (i.e. runs). """
        message_text = ''
        for run in runs:
            if 'text' in run:
                message_text += run['text']
            elif 'emoji' in run:
                message_text += run['emoji']['shortcuts'][0]
            else:
                raise ValueError('Unknown run: {}'.format(run))

        return message_text

    def __get_initial_youtube_info(self, video_id):
        """ Get initial YouTube video information. """
        original_url = 'https://www.youtube.com/watch?v={}'.format(video_id)
        html = self.__session_get(original_url)
        soup = bs4.BeautifulSoup(html.text, 'html.parser')
        ytInitialData_script = next(script.string for script in soup.find_all(
            'script') if script.string and 'ytInitialData' in script.string)
        json_data = next(line.strip()[len('window["ytInitialData"] = '):-1]
                         for line in ytInitialData_script.splitlines() if 'ytInitialData' in line)

        try:
            ytInitialData = json.loads(json_data)
        except Exception as e:
            try:
                # for some reason, it sometimes cuts out and this fixes it
                ytInitialData = json.loads('{"resp'+json_data)
            except Exception:
                raise ParsingError(
                    'Unable to parse video data. Please try again.')

        if('contents' not in ytInitialData):
            raise VideoUnavailable('Video is unavailable (may be private).')

        columns = ytInitialData['contents']['twoColumnWatchNextResults']

        if('conversationBar' not in columns or 'liveChatRenderer' not in columns['conversationBar']):
            error_message = 'Video does not have a chat replay.'
            try:
                error_message = self.__parse_message_runs(
                    columns['conversationBar']['conversationBarRenderer']['availabilityMessage']['messageRenderer']['text']['runs'])
            finally:
                raise NoChatReplay(error_message)

        livechat_header = columns['conversationBar']['liveChatRenderer']['header']
        viewselector_submenuitems = livechat_header['liveChatHeaderRenderer'][
            'viewSelector']['sortFilterSubMenuRenderer']['subMenuItems']

        continuation_by_title_map = {
            x['title']: x['continuation']['reloadContinuationData']['continuation']
            for x in viewselector_submenuitems
        }

        return continuation_by_title_map

    def __get_replay_info(self, continuation, offset_microseconds):
        """Get YouTube replay info, given a continuation or a certain offset."""
        url = self.__YOUTUBE_API_BASE_TEMPLATE.format(
            'live_chat_replay', 'get_live_chat_replay', continuation) + self.__YOUTUBE_API_PARAMETERS_TEMPLATE.format(offset_microseconds)
        return self.__get_continuation_info(url)

    def __get_live_info(self, continuation):
        """Get YouTube live info, given a continuation."""
        url = self.__YOUTUBE_API_BASE_TEMPLATE.format(
            'live_chat', 'get_live_chat', continuation)
        return(self.__get_continuation_info(url))

    def __get_continuation_info(self, url):
        """Get continuation info for a YouTube video."""
        info = self.__session_get_json(url)
        if('continuationContents' in info['response']):
            return info['response']['continuationContents']['liveChatContinuation']
        else:
            raise NoContinuation

    def __ensure_seconds(self, time, default=0):
        """Ensure time is returned in seconds."""
        try:
            return int(time)
        except ValueError:
            return self.__time_to_seconds(time)
        except:
            return default

    def __parse_item(self, item):
        """Parse YouTube item information."""
        data = {}
        index = list(item.keys())[0]
        item_info = item[index]

        # Never before seen index, may cause error (used for debugging)
        if(index not in self.__TYPES_OF_KNOWN_MESSAGES):
            pass

        important_item_info = {key: value for key, value in item_info.items(
        ) if key in self.__IMPORTANT_KEYS_AND_REMAPPINGS}

        data.update(important_item_info)

        for key in important_item_info:
            new_key = self.__IMPORTANT_KEYS_AND_REMAPPINGS[key]
            data[new_key] = data.pop(key)

            # get simpleText if it exists
            if(type(data[new_key]) is dict and 'simpleText' in data[new_key]):
                data[new_key] = data[new_key]['simpleText']

        if('authorBadges' in item_info):
            badges = []
            for badge in item_info['authorBadges']:
                if('liveChatAuthorBadgeRenderer' in badge and 'tooltip' in badge['liveChatAuthorBadgeRenderer']):
                    badges.append(
                        badge['liveChatAuthorBadgeRenderer']['tooltip'])
            data['badges'] = ', '.join(badges)

        if('showItemEndpoint' in item_info):  # has additional information
            data.update(self.__parse_item(
                item_info['showItemEndpoint']['showLiveChatItemEndpoint']['renderer']))
            return data

        data['message'] = self.__parse_message_runs(
            data['message']['runs']) if 'message' in data else None

        data['timestamp'] = int(
            data['timestamp']) if 'timestamp' in data else None
        data['time_in_seconds'] = int(
            self.__time_to_seconds(data['time_text'])) if 'time_text' in data else None

        for colour_key in ('header_color', 'body_color'):
            if(colour_key in data):
                data[colour_key] = self.__get_colours(data[colour_key])

        return data

    def get_youtube_messages(self, video_id, start_time=0, end_time=None, message_type='messages', chat_type='live', callback=None):
        """ Get chat messages for a YouTube video. """

        start_time = self.__ensure_seconds(start_time, 0)
        end_time = self.__ensure_seconds(end_time, None)

        messages = []

        offset_milliseconds = start_time * 1000 if start_time > 0 else 0

        continuation_by_title_map = self.__get_initial_youtube_info(video_id)

        # Top chat replay - Some messages, such as potential spam, may not be visible
        # Live chat replay - All messages are visible
        chat_type_field = chat_type.title()
        chat_replay_field = '{} chat replay'.format(chat_type_field)
        chat_live_field = '{} chat'.format(chat_type_field)

        if(chat_replay_field in continuation_by_title_map):
            is_live = False
            continuation_title = chat_replay_field
        elif(chat_live_field in continuation_by_title_map):
            is_live = True
            continuation_title = chat_live_field
        else:
            raise NoChatReplay('Video does not have a chat replay.')

        continuation = continuation_by_title_map[continuation_title]

        first_time = True
        try:
            while True:
                try:
                    if(is_live):
                        info = self.__get_live_info(continuation)

                        if('actions' not in info):
                            continuation_info = info['continuations'][0]
                            continuation_info = continuation_info[next(
                                iter(continuation_info))]

                            if 'timeoutMs' in continuation_info:
                                # must wait before calling again
                                # prevents 429 errors (too many requests)
                                time.sleep(continuation_info['timeoutMs']/1000)

                            continue  # may have more messages for live chat

                    else:

                        # must run to get first few messages, otherwise might miss some
                        if(first_time):
                            info = self.__get_replay_info(continuation, 0)
                            first_time = False
                        else:
                            info = self.__get_replay_info(
                                continuation, offset_milliseconds)

                        if('actions' not in info):
                            break  # no more messages for chat replay

                except NoContinuation:
                    print('No continuation found, stream may have ended.')
                    break

                for action in info['actions']:
                    data = {}

                    if('replayChatItemAction' in action):
                        replay_chat_item_action = action['replayChatItemAction']
                        if('videoOffsetTimeMsec' in replay_chat_item_action):
                            data['video_offset_time_msec'] = int(
                                replay_chat_item_action['videoOffsetTimeMsec'])
                        action = replay_chat_item_action['actions'][0]

                    action_name = list(action.keys())[0]
                    if('item' not in action[action_name]):
                        # not a valid item to display (usually message deleted)
                        continue

                    item = action[action_name]['item']
                    index = list(item.keys())[0]

                    if(index in self.__TYPES_OF_MESSAGES['ignore']):
                        # can ignore message (not a chat message)
                        continue

                    # user wants everything, keep going
                    if(message_type == 'all'):
                        pass

                    # user does not want superchat + message is superchat
                    elif(message_type != 'superchat' and index in self.__TYPES_OF_MESSAGES['superchat_message'] + self.__TYPES_OF_MESSAGES['superchat_ticker']):
                        continue

                    # user does not want normal messages + message is normal
                    elif(message_type != 'messages' and index in self.__TYPES_OF_MESSAGES['message']):
                        continue

                    data = dict(self.__parse_item(item), **data)

                    time_in_seconds = data['time_in_seconds']
                    if(end_time is not None and time_in_seconds > end_time):
                        return messages

                    if(is_live or time_in_seconds >= start_time):
                        messages.append(data)

                        if(callback is None):
                            # print if it is not a ticker message (prevents duplicates)
                            if(index not in self.__TYPES_OF_MESSAGES['superchat_ticker']):
                                self.print_item(data)

                        elif(callable(callback)):
                            try:
                                callback(data)
                            except TypeError:
                                raise CallbackFunction(
                                    'Incorrect number of parameters for function '+callback.__name__)

                continuation_info = info['continuations'][0]
                for key in ('invalidationContinuationData', 'timedContinuationData', 'liveChatReplayContinuationData'):
                    if key in continuation_info:
                        continuation = continuation_info[key]['continuation']

            return messages

        except KeyboardInterrupt:
            return messages

    def get_twitch_messages(self, video_id, start_time=0, end_time=None, callback=None):
        start_time = self.__ensure_seconds(start_time, 0)
        end_time = self.__ensure_seconds(end_time, None)

        messages = []
        api_url = self.__TWITCH_API_TEMPLATE.format(
            video_id, self.__TWITCH_CLIENT_ID)

        cursor = ''
        try:
            while True:
                url = '{}&cursor={}&content_offset_seconds={}'.format(
                    api_url, cursor, start_time)
                info = self.__session_get_json(url)

                if('error' in info):
                    raise TwitchError(info['message'])

                for comment in info['comments']:
                    time_in_seconds = float(comment['content_offset_seconds'])
                    if(time_in_seconds < start_time):
                        continue

                    if(end_time is not None and time_in_seconds > end_time):
                        return messages

                    created_at = comment['created_at']

                    data = {
                        'timestamp': self.__timestamp_to_microseconds(created_at),
                        'time_text': self.__seconds_to_time(int(time_in_seconds)),
                        'time_in_seconds': time_in_seconds,
                        'author': comment['commenter']['display_name'],
                        'message': comment['message']['body']
                    }

                    messages.append(data)

                    if(callback is None):
                        self.print_item(data)

                    elif(callable(callback)):
                        try:
                            callback(data)
                        except TypeError:
                            raise CallbackFunction(
                                'Incorrect number of parameters for function '+callback.__name__)

                if '_next' in info:
                    cursor = info['_next']
                else:
                    return messages
        except KeyboardInterrupt:
            return messages

    def get_chat_replay(self, url, start_time=0, end_time=None, message_type='messages', chat_type='live', callback=None):
        match = re.search(self.__YT_REGEX, url)
        if(match):
            return self.get_youtube_messages(match.group(1), start_time, end_time, message_type, chat_type, callback)

        match = re.search(self.__TWITCH_REGEX, url)
        if(match):
            return self.get_twitch_messages(match.group(1), start_time, end_time, callback)

        raise InvalidURL('The url provided ({}) is invalid.'.format(url))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='A simple tool used to retrieve YouTube/Twitch chat from past broadcasts/VODs. No authentication needed!',
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('url', help='YouTube/Twitch video URL')

    parser.add_argument('-start_time', '-from', default=0,
                        help='start time in seconds or hh:mm:ss\n(default: %(default)s)')
    parser.add_argument('-end_time', '-to', default=None,
                        help='end time in seconds or hh:mm:ss\n(default: %(default)s = until the end)')

    parser.add_argument('-message_type', choices=['messages', 'superchat', 'all'], default='messages',
                        help='types of messages to include [YouTube only]\n(default: %(default)s)')

    parser.add_argument('-chat_type', choices=['live', 'top'], default='live',
                        help='which chat to get messages from [YouTube only]\n(default: %(default)s)')

    parser.add_argument('-output', '-o', default=None,
                        help='name of output file\n(default: %(default)s = print to standard output)')

    parser.add_argument('-cookies', '-c', default=None,
                        help='name of cookies file\n(default: %(default)s)')

    parser.add_argument('--hide_output', '--h', action='store_true',
                        help='whether to hide output or not\n(default: %(default)s)')

    args = parser.parse_args()

    try:
        chat_downloader = ChatReplayDownloader(cookies=args.cookies)

        num_of_messages = 0

        def do_nothing(item):
            pass

        def print_item(item):
            chat_downloader.print_item(item)

        def write_to_file(item):
            global num_of_messages

            # only file format capable of appending properly
            with open(args.output, 'a', encoding='utf-8') as f:
                if('ticker_duration' not in item):  # needed for duplicates
                    num_of_messages += 1
                    if(not args.hide_output):
                        print_item(item)
                    text = chat_downloader.message_to_string(item)
                    print(text, file=f)

        callback = do_nothing if args.hide_output else (
            None if args.output is None else print_item)
        if(args.output is not None):
            if(args.output.endswith('.json')):
                pass
            elif(args.output.endswith('.csv')):
                fieldnames = []
            else:
                open(args.output, 'w').close()  # empty the file
                callback = write_to_file

        chat_messages = chat_downloader.get_chat_replay(
            args.url,
            start_time=args.start_time,
            end_time=args.end_time,
            message_type=args.message_type,
            chat_type=args.chat_type,
            callback=callback
        )

        if(args.output is not None):
            if(args.output.endswith('.json')):
                num_of_messages = len(chat_messages)
                with open(args.output, 'w') as f:
                    json.dump(chat_messages, f, sort_keys=True)

            elif(args.output.endswith('.csv')):
                num_of_messages = len(chat_messages)
                fieldnames = []
                for message in chat_messages:
                    fieldnames = list(set(fieldnames + list(message.keys())))

                with open(args.output, 'w', newline='', encoding='utf-8') as f:
                    fc = csv.DictWriter(f, fieldnames=fieldnames)
                    fc.writeheader()
                    fc.writerows(chat_messages)

            print('Finished writing', num_of_messages,
                  'messages to', args.output)

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

else:
    # when used as a module
    def get_chat_replay(url, start_time=0, end_time=None, message_type='messages', chat_type='live', callback=None):
        return ChatReplayDownloader().get_chat_replay(url, start_time, end_time, message_type, chat_type, callback)

    def get_youtube_messages(url, start_time=0, end_time=None, message_type='messages', chat_type='live', callback=None):
        return ChatReplayDownloader().get_youtube_messages(url, start_time, end_time, message_type, chat_type, callback)

    def get_twitch_messages(url, start_time=0, end_time=None, callback=None):
        return ChatReplayDownloader().get_twitch_messages(url, start_time, end_time, callback)
