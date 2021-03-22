#!/usr/bin/env python3
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
import random
import json
import datetime
import re
import argparse
import csv
import emoji
import time
import os
from http.cookiejar import MozillaCookieJar, LoadError
import sys
import codecs
from urllib import parse


# add TRACE log level
if not hasattr(logging, 'TRACE') or 'TRACE' not in logging._nameToLevel:
    logging.TRACE = logging.DEBUG // 2
    logging.addLevelName(logging.TRACE, 'TRACE')
if not hasattr(logging, 'trace') or not hasattr(logging.Logger, 'trace') or not hasattr(logging.LoggerAdapter, 'trace'):
    def __trace(self, msg, *args, **kwargs):
        self.log(logging.TRACE, msg, *args, **kwargs)
    logging.trace = __trace
    logging.Logger.trace = __trace
    logging.LoggerAdapter.trace = __trace


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

    DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

    __HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36',
        'Accept-Language': 'en-US, en'
    }

    __YT_HOME = 'https://www.youtube.com'
    __YT_REGEX = r'(?:/|%3D|v=|vi=)([0-9A-z-_]{11})(?:[%#?&]|$)'
    __YOUTUBE_API_BASE_TEMPLATE = '{}/youtubei/{}/live_chat/{}?key={}'

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
        'superchat': [
            # superchat messages which appear in chat
            'liveChatMembershipItemRenderer',
            'liveChatPaidMessageRenderer',
            'liveChatPaidStickerRenderer'
            # superchat messages which appear ticker (at the top)
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

    # 1) provides a formatter that adds context to log messages
    # 2) allows string.format-style ({}-style) formatting (rather than %-style formatting)
    # 3) provides a decorator that has context be the video id passed to the decorated function
    #    decorator functions defined in a class can't be used to decorate a function in the same class, so this separate class provides a workaround
    class ContextLogger(logging.LoggerAdapter):
        def __init__(self, logger):
            logger.propagate = False
            if not logger.hasHandlers():
                handler = logging.StreamHandler(sys.stdout)
                handler.setFormatter(logging.Formatter('[%(levelname)s][%(asctime)s]%(context)s %(message)s', datefmt=ChatReplayDownloader.DATETIME_FORMAT))
                logger.addHandler(handler)
            super().__init__(logger, None)
            self.context = ''

        def log(self, level, msg, *args, **kwargs):
            if self.isEnabledFor(level):
                kwargs['extra'] = self.__dict__
                if args:
                    msg = msg.format(*args)
                self.logger._log(level, msg, (), **kwargs)

        @classmethod
        def log_video_id(cls, func):
            def wrapped(self, video_id, *args, **kwargs):
                if not isinstance(self.logger, cls):
                    raise TypeError(f"self.logger must be {cls.__qualname__} - was {self.logger.__class__.__qualname__}")
                orig_context = self.logger.context
                self.logger.context = f"[{video_id}]"
                try:
                    return func(self, video_id, *args, **kwargs)
                finally:
                    self.logger.context = orig_context
            return wrapped

    def __init__(self, cookies=None, log_level=logging.WARNING):
        """Initialise a new session for making requests."""
        self.logger = self.ContextLogger(logging.getLogger(self.__class__.__name__))
        self.logger.setLevel(log_level)

        self.session = requests.Session()
        self.session.headers = self.__HEADERS

        Retry.BACKOFF_MAX = 2 ** 5
        self.session.mount('https://', HTTPAdapter(max_retries=Retry(
            total=10,
            # Retry doesn't have jitter functionality; following random usage is a poor man's version that only jitters backoff_factor across sessions.
            backoff_factor=random.uniform(1.0, 1.5),
            status_forcelist=[413, 429, 500, 502, 503, 504], # also retries on connection/read timeouts
            method_whitelist=False))) # retry on any HTTP method (including GET and POST)

        cj = MozillaCookieJar(cookies)
        if cookies is not None:
            # Only attempt to load if the cookie file exists.
            if os.path.exists(cookies):
                cj.load(ignore_discard=True, ignore_expires=True)
            else:
                raise CookieError(
                    "The file '{}' could not be found.".format(cookies))
        self.session.cookies = cj

    def __session_get(self, url, post_payload=None):
        """Make a request using the current session."""
        if post_payload is None:
            response = self.session.get(url, timeout=10)
        else:
            if self.logger.isEnabledFor(logging.TRACE): # guard since json.dumps is expensive
                self.logger.trace("HTTP POST {!r} <= body JSON (pretty-printed):\n{}", url, json.dumps(post_payload, indent=4)) # too verbose
            post_payload = json.dumps(post_payload)
            response = self.session.post(url, data=post_payload, timeout=10)
        return response

    def __session_get_json(self, url, post_payload=None):
        """Make a request using the current session and get json data."""
        try:
            ret = self.__session_get(url, post_payload).json()
        except json.JSONDecodeError as e:
            raise ParsingError("Could not parse JSON from response to {!r}:\n{}".format(url, e.doc)) from e
        if self.logger.isEnabledFor(logging.TRACE): # guard since json.dumps is expensive
            self.logger.trace("HTTP {} {!r} => response JSON:\n{}", 'GET' if post_payload is None else 'POST', url, json.dumps(ret, indent=4))
        return ret

    def __timestamp_to_microseconds(self, timestamp):
        """
        Convert RFC3339 timestamp to microseconds.
        This is needed as datetime.datetime.strptime() does not support nanosecond precision.
        """
        info = list(filter(None, re.split(r'[\.|Z]{1}', timestamp))) + [0]
        return round((datetime.datetime.strptime('{}Z'.format(info[0]), '%Y-%m-%dT%H:%M:%SZ').timestamp() + float('0.{}'.format(info[1])))*1e6)

    def __time_to_seconds(self, time):
        """Convert timestamp string of the form 'hh:mm:ss' to seconds."""
        return sum(abs(int(x)) * 60 ** i for i, x in enumerate(reversed(time.replace(',', '').split(':')))) * (-1 if time[0] == '-' else 1)

    def __seconds_to_time(self, seconds):
        """Convert seconds to timestamp."""
        return re.sub(r'^0:0?', '', str(datetime.timedelta(0, seconds)))

    def __microseconds_to_timestamp(self, microseconds):
        """Convert unix time to human-readable timestamp."""
        return datetime.datetime.fromtimestamp(microseconds//1000000).strftime(self.DATETIME_FORMAT)

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
        """
        Format item for printing to standard output.
        [datetime] (author_type) *money* author: message,
        where (author_type) and *money* are optional.
        """
        return '[{}] {}{}{}:\t{}'.format(
            item['datetime'] if 'datetime' in item else (
                item['time_text'] if 'time_text' in item else ''),
            '({}) '.format(item['author_type'].lower()) if 'author_type' in item else '',
            '*{}* '.format(item['amount']) if 'amount' in item else '',
            item.get('author', ''),
            item.get('message', '')
        )

    def print_item(self, item):
        """
        Ensure printing to standard output can be done safely (especially on Windows).
        There are usually issues with printing emojis and non utf-8 characters.
        """
        # Don't print if it is a ticker message (prevents duplicates)
        if 'ticker_duration' in item:
            return

        message = emoji.demojize(self.message_to_string(item))

        try:
            safe_string = message.encode(
                'utf-8', 'ignore').decode('utf-8', 'ignore')
            print(safe_string, flush=True)
        except UnicodeEncodeError:
            # in the rare case that standard output does not support utf-8
            safe_string = message.encode(
                'ascii', 'ignore').decode('ascii', 'ignore')
            print(safe_string, flush=True)

    def __parse_youtube_link(self, text):
        if text.startswith(('/redirect', 'https://www.youtube.com/redirect')):  # is a redirect link
            info = dict(parse.parse_qsl(parse.urlsplit(text).query))
            return info.get('q') or ''
        elif text.startswith('//'):
            return 'https:' + text
        elif text.startswith('/'):  # is a youtube link e.g. '/watch','/results'
            return self.__YT_HOME + text
        else:  # is a normal link
            return text

    def __parse_message_runs(self, runs):
        """ Reads and parses YouTube formatted messages (i.e. runs). """
        message_text = ''
        for run in runs:
            if 'text' in run:
                if 'navigationEndpoint' in run:  # is a link
                    try:
                        url = run['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url']
                        message_text += self.__parse_youtube_link(url)
                    except:
                        # if something fails, use default text
                        message_text += run['text']

                else:  # is a normal message
                    message_text += run['text']
            elif 'emoji' in run:
                message_text += run['emoji']['shortcuts'][0]
            else:
                message_text += str(run)

        return message_text

    _YT_CFG_RE = re.compile(r'\bytcfg\s*\.\s*set\(\s*({.*})\s*\)\s*;')
    _YT_INITIAL_PLAYER_RESPONSE_RE = re.compile(r'\bytInitialPlayerResponse\s*=\s*({.+?})\s*;')
    _YT_INITIAL_DATA_RE = re.compile(r'(?:\bwindow\s*\[\s*["\']ytInitialData["\']\s*\]|\bytInitialData)\s*=\s*(\{.+\})\s*;')
    def __get_initial_youtube_info(self, video_id):
        """ Get initial YouTube video information. """
        original_url = '{}/watch?v={}'.format(self.__YT_HOME, video_id)
        html = self.__session_get(original_url)

        json_decoder = json.JSONDecoder() # for more lenient raw_decode usage

        m = self._YT_CFG_RE.search(html.text)
        if not m:
            raise ParsingError('Unable to parse video data. Please try again.')
        ytcfg, _ = json_decoder.raw_decode(m.group(1))
        if self.logger.isEnabledFor(logging.TRACE): # guard since json.dumps is expensive
            self.logger.trace("ytcfg:\n{}", json.dumps(ytcfg, indent=4))

        config = {
            'api_version': ytcfg['INNERTUBE_API_VERSION'],
            'api_key': ytcfg['INNERTUBE_API_KEY'],
            'context': ytcfg['INNERTUBE_CONTEXT'],
        }

        m = self._YT_INITIAL_PLAYER_RESPONSE_RE.search(html.text)
        if not m:
            raise ParsingError('Unable to parse video data. Please try again.')
        ytInitialPlayerResponse, _ = json_decoder.raw_decode(m.group(1))
        if self.logger.isEnabledFor(logging.TRACE):
            self.logger.trace("ytInitialPlayerResponse:\n{}", json.dumps(ytInitialPlayerResponse, indent=4))

        config['is_upcoming'] = ytInitialPlayerResponse.get('videoDetails', {}).get('isUpcoming', False)

        m = self._YT_INITIAL_DATA_RE.search(html.text)
        if not m:
            raise ParsingError('Unable to parse video data. Please try again.')

        ytInitialData, _ = json_decoder.raw_decode(m.group(1))
        if self.logger.isEnabledFor(logging.TRACE):
            self.logger.trace("ytInitialData:\n{}", json.dumps(ytInitialData, indent=4))

        contents = ytInitialData.get('contents')
        if(not contents):
            raise VideoUnavailable('Video is unavailable (may be private).')

        columns = contents.get('twoColumnWatchNextResults')

        if('conversationBar' not in columns or 'liveChatRenderer' not in columns['conversationBar']):
            error_message = 'Video does not have a chat replay.'
            try:
                error_message = self.__parse_message_runs(
                    columns['conversationBar']['conversationBarRenderer']['availabilityMessage']['messageRenderer']['text']['runs'])
            except KeyError:
                pass
            config['no_chat_error'] = error_message
            continuation_by_title_map = {}
        else:
            livechat_header = columns['conversationBar']['liveChatRenderer']['header']
            viewselector_submenuitems = livechat_header['liveChatHeaderRenderer'][
                'viewSelector']['sortFilterSubMenuRenderer']['subMenuItems']
            continuation_by_title_map = {
                x['title']: x['continuation']['reloadContinuationData']['continuation']
                for x in viewselector_submenuitems
            }

        return config, continuation_by_title_map

    def __get_replay_info(self, config, continuation, offset_milliseconds):
        """Get YouTube replay info, given a continuation or a certain offset."""
        url = self.__YOUTUBE_API_BASE_TEMPLATE.format(self.__YT_HOME, config['api_version'], 'get_live_chat_replay', config['api_key'])
        self.logger.debug("get_replay_info: continuation={}, playerOffsetMs={}", continuation, offset_milliseconds)
        return self.__get_continuation_info(url, {
            'context': config['context'],
            'continuation': continuation,
            'currentPlayerState': {
                'playerOffsetMs': str(offset_milliseconds),
            },
        })

    def __get_live_info(self, config, continuation):
        """Get YouTube live info, given a continuation."""
        url = self.__YOUTUBE_API_BASE_TEMPLATE.format(self.__YT_HOME, config['api_version'], 'get_live_chat', config['api_key'])
        self.logger.debug("get_live_info: continuation={}", continuation)
        return self.__get_continuation_info(url, {
            'context': config['context'],
            'continuation': continuation,
        })

    def __get_continuation_info(self, url, payload):
        """Get continuation info for a YouTube video."""
        response = self.__session_get_json(url, payload)
        error = response.get('error')
        if error:
            # Error code 403 'The caller does not have permission' error likely means the stream was privated immediately while the chat is still active.
            error_code = error.get('code')
            if error_code == 403:
                raise VideoUnavailable
            elif error_code == 404:
                raise VideoNotFound
            else:
                raise ParsingError("JSON response to {!r} is error:\n{}".format(url, json.dumps(response, indent=4)))
        info = response.get('continuationContents', {}).get('liveChatContinuation')
        if info:
            return info
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

    __AUTHORTYPE_ORDER_MAP = {value: index for index, value in enumerate(('', 'VERIFIED', 'MEMBER', 'MODERATOR', 'OWNER'))}
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

        author_badges = item_info.get('authorBadges')
        if author_badges:
            badges = []
            author_type = ''
            for badge in author_badges:
                badge_renderer = badge.get('liveChatAuthorBadgeRenderer')
                if badge_renderer:
                    tooltip = badge_renderer.get('tooltip')
                    icon_type = badge_renderer.get('icon', {}).get('iconType')
                    if tooltip:
                        badges.append(tooltip)
                        if not icon_type:
                            icon_type = 'MEMBER'
                    if icon_type and (author_type == '' or self.__AUTHORTYPE_ORDER_MAP.get(icon_type, 0) >= self.__AUTHORTYPE_ORDER_MAP.get(author_type, 0)):
                        author_type = icon_type
            data['badges'] = ', '.join(badges)
            data['author_type'] = author_type

        if('showItemEndpoint' in item_info):  # has additional information
            data.update(self.__parse_item(
                item_info['showItemEndpoint']['showLiveChatItemEndpoint']['renderer']))
            return data

        data['message'] = self.__parse_message_runs(
            data['message']['runs']) if 'message' in data else None

        timestamp = data.get('timestamp')
        if timestamp:
            timestamp = int(timestamp)
            data['timestamp'] = timestamp
            data['datetime'] = self.__microseconds_to_timestamp(timestamp)

        if('time_text' in data):
            data['time_in_seconds'] = int(
                self.__time_to_seconds(data['time_text']))

        for colour_key in ('header_color', 'body_color'):
            if(colour_key in data):
                data[colour_key] = self.__get_colours(data[colour_key])

        return data

    @ContextLogger.log_video_id
    def get_youtube_messages(self, video_id, start_time=0, end_time=None, message_type='messages', chat_type='live', callback=None, **kwargs):
        """ Get chat messages for a YouTube video. """

        start_time = self.__ensure_seconds(start_time, 0)
        end_time = self.__ensure_seconds(end_time, None)

        messages = []

        offset_milliseconds = start_time * 1000 if start_time > 0 else 0

        # Top chat replay - Some messages, such as potential spam, may not be visible
        # Live chat replay - All messages are visible
        chat_type_field = chat_type.title()
        chat_replay_field = '{} chat replay'.format(chat_type_field)
        chat_live_field = '{} chat'.format(chat_type_field)

        try:
            continuation_title = None
            attempt_ct = 0
            while True:
                attempt_ct += 1
                config, continuation_by_title_map = self.__get_initial_youtube_info(video_id)

                if(chat_replay_field in continuation_by_title_map):
                    is_live = False
                    continuation_title = chat_replay_field
                elif(chat_live_field in continuation_by_title_map):
                    is_live = True
                    continuation_title = chat_live_field

                if continuation_title is None:
                    error_message = config.get('no_chat_error', 'Video does not have a chat replay.')
                    if config['is_upcoming']:
                        retry_wait_secs = random.randint(30, 45) # jitter
                        self.logger.debug("Upcoming {} Retrying in {} secs (attempt {})", error_message, retry_wait_secs, attempt_ct)
                        time.sleep(retry_wait_secs)
                    else:
                        raise NoChatReplay(error_message)
                else:
                    if self.logger.isEnabledFor(logging.DEBUG): # guard since json.dumps is expensive
                        self.logger.debug("config:\n{}", json.dumps(config, indent=4))
                        self.logger.debug("continuation_by_title_map:\n{}", json.dumps(continuation_by_title_map, indent=4))
                    break

            continuation = continuation_by_title_map[continuation_title]

            first_time = True
            while True:
                try:
                    if(is_live):
                        info = self.__get_live_info(config, continuation)
                    else:
                        # must run to get first few messages, otherwise might miss some
                        if(first_time):
                            info = self.__get_replay_info(config, continuation, 0)
                            first_time = False
                        else:
                            info = self.__get_replay_info(config, continuation, offset_milliseconds)

                except NoContinuation:
                    print('No continuation found, stream may have ended.')
                    break

                except VideoUnavailable:
                    print('Video not unavailable, stream may have been privated while live chat was still active.')
                    break

                except VideoNotFound:
                    print('Video not found, stream may have been deleted while live chat was still active.')
                    break

                if('actions' in info):
                    for action in info['actions']:
                        data = {}

                        if('replayChatItemAction' in action):
                            replay_chat_item_action = action['replayChatItemAction']
                            if('videoOffsetTimeMsec' in replay_chat_item_action):
                                data['video_offset_time_msec'] = int(
                                    replay_chat_item_action['videoOffsetTimeMsec'])
                            action = replay_chat_item_action['actions'][0]

                        action.pop('clickTrackingParams', None)
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
                        elif(message_type != 'superchat' and index in self.__TYPES_OF_MESSAGES['superchat']):
                            continue

                        # user does not want normal messages + message is normal
                        elif(message_type != 'messages' and index in self.__TYPES_OF_MESSAGES['message']):
                            continue

                        data = dict(self.__parse_item(item), **data)

                        time_in_seconds = data['time_in_seconds'] if 'time_in_seconds' in data else None

                        valid_seconds = time_in_seconds is not None
                        if(end_time is not None and valid_seconds and time_in_seconds > end_time):
                            return messages

                        if(is_live or (valid_seconds and time_in_seconds >= start_time)):
                            messages.append(data)

                            if(callback is None):
                                self.print_item(data)

                            elif(callable(callback)):
                                try:
                                    callback(data)
                                except TypeError:
                                    raise CallbackFunction(
                                        'Incorrect number of parameters for function '+callback.__name__)
                else:
                    # no more actions to process in a chat replay
                    if(not is_live):
                        break

                if('continuations' in info):
                    continuation_info = info['continuations'][0]
                    # possible continuations:
                    # invalidationContinuationData, timedContinuationData,
                    # liveChatReplayContinuationData, reloadContinuationData
                    continuation_info = continuation_info[next(
                        iter(continuation_info))]

                    if 'continuation' in continuation_info:
                        continuation = continuation_info['continuation']
                    if 'timeoutMs' in continuation_info:
                        # must wait before calling again
                        # prevents 429 errors (too many requests)
                        self.logger.trace("continuation timeoutMs={}", continuation_info['timeoutMs'])
                        time.sleep(continuation_info['timeoutMs']/1000)
                else:
                    break

            return messages

        except KeyboardInterrupt:
            print('[Interrupted]', flush=True)
            return messages

    @ContextLogger.log_video_id
    def get_twitch_messages(self, video_id, start_time=0, end_time=None, callback=None, **kwargs):
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
            print('[Interrupted]', flush=True)
            return messages

    def get_chat_replay(self, url, start_time=0, end_time=None, message_type='messages', chat_type='live', callback=None, **kwargs):
        match = re.search(self.__YT_REGEX, url)
        if(match):
            return self.get_youtube_messages(match.group(1), start_time, end_time, message_type, chat_type, callback, **kwargs)

        match = re.search(self.__TWITCH_REGEX, url)
        if(match):
            return self.get_twitch_messages(match.group(1), start_time, end_time, callback, **kwargs)

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

    parser.add_argument('--hide_output', action='store_true',
                        help='whether to hide output or not\n(default: %(default)s)')

    parser.add_argument('-log_level',
                        choices=[name for level, name in logging._levelToName.items() if level != 0],
                        default=logging._levelToName[logging.WARNING],
                        help='log level, logged to standard output\n(default: %(default)s)')

    args = parser.parse_args()

    if(args.hide_output):
        f = open(os.devnull, 'w')
        sys.stdout = f
        sys.stderr = f
    else:
        # set encoding of standard output and standard error
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

    # this has to go after stdout/stderr are modified
    logging.basicConfig(level=args.log_level, stream=sys.stdout, format='[%(levelname)s][%(asctime)s][%(name)s] %(message)s',
                        datefmt=ChatReplayDownloader.DATETIME_FORMAT)

    num_of_messages = 0
    chat_messages = []

    try:
        chat_downloader = ChatReplayDownloader(cookies=args.cookies, log_level=args.log_level)

        def print_item(item):
            chat_downloader.print_item(item)

        def write_to_file(item):
            global num_of_messages

            # Don't print if it is a ticker message (prevents duplicates)
            if 'ticker_duration' in item:
                return

            # only file format capable of appending properly
            with open(args.output, 'a', newline='', encoding='utf-8-sig') as f:
                num_of_messages += 1
                print_item(item)
                text = chat_downloader.message_to_string(item)
                print(text, file=f)

        callback = None if args.output is None else print_item
        if(args.output is not None):
            if(args.output.endswith('.json')):
                pass
            elif(args.output.endswith('.csv')):
                fieldnames = []
            else:
                open(args.output, 'w').close()  # empty the file
                callback = write_to_file

        chat_messages = chat_downloader.get_chat_replay(callback=callback, **vars(args))

    except InvalidURL as e:
        print('[Invalid URL]', e, flush=True)
    except ParsingError as e:
        print('[Parsing Error]', e, flush=True)
    except NoChatReplay as e:
        print('[No Chat Replay]', e, flush=True)
    except VideoUnavailable as e:
        print('[Video Unavailable]', e, flush=True)
    except TwitchError as e:
        print('[Twitch Error]', e, flush=True)
    except (LoadError, CookieError) as e:
        print('[Cookies Error]', e, flush=True)
    except requests.exceptions.RequestException:
        print('[HTTP Request Error]', e, flush=True)
    except KeyboardInterrupt:
        print('[Interrupted]', flush=True)
    # XXX ctrl-c sometimes isn't caught by above KeyboardInterrupt and/or exits the program before finally block runs,
    # possibly due to a sys.exit or interrupt in some library code?
    except SystemExit as e:
        print('[Unexpected SystemExit]', e, flush=True)
    except InterruptedError as e:
        print('[Unexpected InterruptedError]', e, flush=True)

    finally:
        if chat_messages and args.output:
            if(args.output.endswith('.json')):
                num_of_messages = len(chat_messages)
                with open(args.output, 'w', newline='', encoding='utf-8-sig') as f:
                    json.dump(chat_messages, f, sort_keys=True)

            elif(args.output.endswith('.csv')):
                num_of_messages = len(chat_messages)
                fieldnames = set()
                for message in chat_messages:
                    fieldnames.update(message.keys())
                fieldnames = sorted(fieldnames)

                with open(args.output, 'w', newline='', encoding='utf-8-sig') as f:
                    fc = csv.DictWriter(f, fieldnames=fieldnames)
                    fc.writeheader()
                    fc.writerows(chat_messages)

            print('Finished writing', num_of_messages,
                'messages to', args.output, flush=True)

else:
    # when used as a module
    def get_chat_replay(url, start_time=0, end_time=None, message_type='messages', chat_type='live', callback=None, **kwargs):
        return ChatReplayDownloader().get_chat_replay(url, start_time, end_time, message_type, chat_type, callback, **kwargs)

    def get_youtube_messages(url, start_time=0, end_time=None, message_type='messages', chat_type='live', callback=None, **kwargs):
        return ChatReplayDownloader().get_youtube_messages(url, start_time, end_time, message_type, chat_type, callback, **kwargs)

    def get_twitch_messages(url, start_time=0, end_time=None, callback=None, **kwargs):
        return ChatReplayDownloader().get_twitch_messages(url, start_time, end_time, callback, **kwargs)
