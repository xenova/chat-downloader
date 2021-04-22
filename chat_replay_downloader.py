#!/usr/bin/env python3
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
import loggingutils
import ioutils
import random
import json
from datetime import datetime, timedelta
import re
import argparse
import csv
import emoji
import time
import os
from http.cookiejar import MozillaCookieJar, LoadError
import sys
import signal
from urllib import parse
import inspect


logging.TRACE, logging.trace, logging.Logger.trace, logging.LoggerAdapter.trace = loggingutils.addLevelName(logging.DEBUG // 2, 'TRACE')


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


class AbortConditionsSatisfied(Exception):
    """"Raised when all abort conditions are satisfied."""
    pass


class ChatReplayDownloader:
    """A simple tool used to retrieve YouTube/Twitch chat from past broadcasts/VODs. No authentication needed!"""

    DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

    # since sys.stdout may change (see main() below), using loggingutils.StdoutHandler to always use latest sys.stdout
    logger = loggingutils.loggerProperty(logger_init=lambda self, *_: loggingutils.FormatLoggerAdapter(self, style='{'),
        propagate=False, handlers=[loggingutils.StdoutHandler()],
        lenient=True, format='[%(levelname)s][%(asctime)s]%(context)s %(message)s', datefmt=DATETIME_FORMAT)

    __HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36',
        'Accept-Language': 'en-US, en'
    }

    __YT_HOME = 'https://www.youtube.com'
    __YT_REGEX = r'(?:/|%3D|v=|vi=)([0-9A-Za-z-_]{11})(?:[%#?&]|$)'
    __YOUTUBE_API_BASE_TEMPLATE = '{}/youtubei/{}/{}?key={}'

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

    def __init__(self, cookies=None):
        """Initialise a new session for making requests."""
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
                self.logger.trace("HTTP POST {!r} <= body JSON (pretty-printed):\n{}", url, _debug_dump(post_payload)) # too verbose
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
            self.logger.trace("HTTP {} {!r} => response JSON:\n{}", 'GET' if post_payload is None else 'POST', url, _debug_dump(ret))
        return ret

    def __timestamp_to_microseconds(self, timestamp):
        """
        Convert RFC3339 timestamp to microseconds.
        This is needed as datetime.strptime() does not support nanosecond precision.
        """
        info = list(filter(None, re.split(r'[\.|Z]{1}', timestamp))) + [0]
        return round((datetime.strptime('{}Z'.format(info[0]), '%Y-%m-%dT%H:%M:%SZ').timestamp() + float('0.{}'.format(info[1])))*1e6)

    def __time_to_seconds(self, time):
        """Convert timestamp string of the form 'hh:mm:ss' to seconds."""
        return sum(abs(int(x)) * 60 ** i for i, x in enumerate(reversed(time.replace(',', '').split(':')))) * (-1 if time[0] == '-' else 1)

    def __seconds_to_time(self, seconds):
        """Convert seconds to timestamp."""
        time_text = str(timedelta(seconds=seconds))
        return time_text if time_text != '0:0' else ''

    def __timestamp_microseconds_to_datetime_str(self, timestamp_microseconds):
        """Convert unix timestamp in microseconds to datetime string."""
        return datetime.fromtimestamp(timestamp_microseconds // 1_000_000).strftime(self.DATETIME_FORMAT)

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
            self.logger.trace("ytcfg:\n{}", _debug_dump(ytcfg))

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
            self.logger.trace("ytInitialPlayerResponse:\n{}", _debug_dump(ytInitialPlayerResponse))

        config['is_upcoming'] = ytInitialPlayerResponse.get('videoDetails', {}).get('isUpcoming', False)
        config['scheduled_start_time'] = self.__get_scheduled_start_time(ytInitialPlayerResponse)

        m = self._YT_INITIAL_DATA_RE.search(html.text)
        if not m:
            raise ParsingError('Unable to parse video data. Please try again.')

        ytInitialData, _ = json_decoder.raw_decode(m.group(1))
        if self.logger.isEnabledFor(logging.TRACE):
            self.logger.trace("ytInitialData:\n{}", _debug_dump(ytInitialData))

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

    def __get_scheduled_start_time(self, info):
        """Get scheduled start time for a YouTube video (from either heartbeat JSON or ytInitialPlayerResponse JSON)."""
        try:
            timestamp = int(info['playabilityStatus']['liveStreamability']['liveStreamabilityRenderer']['offlineSlate']['liveStreamOfflineSlateRenderer']['scheduledStartTime'])
            return datetime.fromtimestamp(timestamp)
        except LookupError:
            return None

    def __get_replay_info(self, config, continuation, offset_milliseconds):
        """Get YouTube replay info, given a continuation or a certain offset."""
        url = self.__YOUTUBE_API_BASE_TEMPLATE.format(self.__YT_HOME, config['api_version'], 'live_chat/get_live_chat_replay', config['api_key'])
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
        url = self.__YOUTUBE_API_BASE_TEMPLATE.format(self.__YT_HOME, config['api_version'], 'live_chat/get_live_chat', config['api_key'])
        self.logger.debug("get_live_info: continuation={}", continuation)
        return self.__get_continuation_info(url, {
            'context': config['context'],
            'continuation': continuation,
        })

    def __get_continuation_info(self, url, payload):
        """Get continuation info for a YouTube video."""
        response = self.__get_youtube_json(url, payload)
        try:
            return response['continuationContents']['liveChatContinuation']
        except LookupError:
            raise NoContinuation

    def __get_heartbeat_info(self, video_id, config):
        """Get heartbeat info for a YouTube video."""
        url = self.__YOUTUBE_API_BASE_TEMPLATE.format(self.__YT_HOME, config['api_version'], 'player/heartbeat', config['api_key'] + '&alt=json')
        payload = {
            'context': config['context'],
            'videoId': video_id,
            'heartbeatRequestParams': {'heartbeatChecks': ['HEARTBEAT_CHECK_TYPE_LIVE_STREAM_STATUS']}
        }
        return self.__get_youtube_json(url, payload)

    def __get_youtube_json(self, url, payload):
        """Get JSON for a YouTube API url"""
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
                raise ParsingError("JSON response to {!r} is error:\n{}".format(url, _debug_dump(response)))
        return response

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
            data['datetime'] = self.__timestamp_microseconds_to_datetime_str(timestamp)

        if('time_text' in data):
            data['time_in_seconds'] = int(
                self.__time_to_seconds(data['time_text']))

        for colour_key in ('header_color', 'body_color'):
            if(colour_key in data):
                data[colour_key] = self.__get_colours(data[colour_key])

        return data

    # used to construct each args.abort_condition option
    # resulting args.abort_condition structure:
    # list of condition groups, where condition group is a list of (condition string (name:arg), condition function) tuples
    # conditions are ANDed within a condition group, and condition groups are ORed
    # any boolean formula can be converted into this OR of ANDs form (a.k.a. disjunctive normal form)
    @classmethod
    def parse_abort_condition_group(cls, raw_cond_group, error_gen=ValueError):
        cond_group = []
        cond_name_dict = {} # for ensuring uniqueness

        raw_conds = list(cls._tokenize_abort_condition_group(raw_cond_group, error_gen))
        for raw_cond in raw_conds:
            raw_cond = raw_cond.strip()
            cond_name, cond_arg = raw_cond.split(':', 1) if ':' in raw_cond else (raw_cond, None)
            if cond_name in cond_name_dict:
                raise error_gen(f"({raw_cond_group}) multiple {cond_name} conditions cannot exist within in the option argument "
                    f"(cannot have both {cond_name_dict[cond_name]!r} and {raw_cond!r})")
            cond_name_dict[cond_name] = raw_cond

            if cond_name == 'changed_scheduled_start_time':
                datetime_format = cond_arg
                # test format round-trip
                try:
                    sample_formatted = datetime.strptime(datetime.now().strftime(datetime_format), datetime_format)
                except ValueError as e:
                    raise error_gen(f"({raw_cond_group}) {e}")
                cls.logger.debug("abort condition {}: format {!r} => e.g. {!r}", cond_name, datetime_format, sample_formatted)
                def changed_scheduled_start_time(orig_scheduled_start_time, curr_scheduled_start_time,
                        # trick to 'fix' the value of variable for this function, since variable changes over loop iterations
                        datetime_format=datetime_format, **_):
                    if not orig_scheduled_start_time or not curr_scheduled_start_time:
                        return None # falsy
                    orig_formatted = orig_scheduled_start_time.strftime(datetime_format)
                    curr_formatted = curr_scheduled_start_time.strftime(datetime_format)
                    if orig_formatted != curr_formatted:
                        return "scheduled start time formatted as {!r} changed from {:{}} to {:{}}".format(
                            datetime_format, orig_scheduled_start_time, datetime_format, curr_scheduled_start_time, datetime_format)
                cond_group.append((raw_cond, changed_scheduled_start_time))

            elif cond_name == 'min_time_until_scheduled_start_time':
                m = re.fullmatch(r'(\d+):(\d+)$', cond_arg)
                if not m:
                    raise error_gen(f"({raw_cond_group}) {cond_name} argument must be in format <hours>:<minutes>, e.g. 01:30")
                min_secs = int(m[1]) * 3600 + int(m[2]) * 60
                cls.logger.debug("abort condition {}: {!r} => min {} secs", cond_name, cond_arg, min_secs)
                def min_time_until_scheduled_start_time(curr_scheduled_start_time,
                        # trick to 'fix' the value of variable for this function, since variable changes over loop iterations
                        min_secs=min_secs, **_):
                    if not curr_scheduled_start_time:
                        return None # falsy
                    secs_until_scheduled_start_time = curr_scheduled_start_time.timestamp() - time.time()
                    if secs_until_scheduled_start_time > min_secs:
                        return f"time until scheduled start time {secs_until_scheduled_start_time} secs >= {min_secs} secs"
                    return None
                cond_group.append((raw_cond, min_time_until_scheduled_start_time))

            else:
                raise error_gen(f"({raw_cond_group}) unrecognized condition: {raw_cond}")

        return cond_group

    # splits on + while handling escapes \\ and \+
    _ABORT_CONDITION_TOKEN_REGEX = re.compile(r'((?:\\.|[^+\\])*)([+]|$)')
    @classmethod
    def _tokenize_abort_condition_group(cls, raw_cond_group, error_gen):
        prev_pos = 0
        for m in cls._ABORT_CONDITION_TOKEN_REGEX.finditer(raw_cond_group):
            if prev_pos != m.start(): # means invalid string (trailing backslash)
                raise error_gen(f"({raw_cond_group}) invalid string (unexpected end of string): {raw_cond_group[prev_pos:]}")
            raw_cond = m[1]
            if len(raw_cond) == 0:
                raise error_gen(f"({raw_cond_group}) condition cannot be empty")
            else:
                yield raw_cond.replace('\\+', '+').replace('\\\\', '\\')
            prev_pos = m.end()
            if len(m[2]) == 0: # matched end of string
                break # next iteration would start at end of string and match empty string, which we want to avoid

    class AbortConditionChecker:
        def __init__(self, logger, cond_groups, **prereq_funcs):
            self.logger = logger
            self.cond_groups = cond_groups
            prereq_names = set(param.name
                for cond_group in cond_groups
                for _, cond_func in cond_group
                for param in inspect.signature(cond_func).parameters.values()
                if param.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD and param.default is inspect.Parameter.empty)
            self.logger.debug("abort condition prereq names: {!r}", prereq_names)
            unmet_prereq_names = prereq_names - set(prereq_funcs.keys())
            if unmet_prereq_names:
                raise RuntimeError(f"unmet prereqs: {', '.join(unmet_prereq_names)}")
            self.prereq_funcs = {prereq_name: prereq_func for prereq_name, prereq_func in prereq_funcs.items() if prereq_name in prereq_names}
            self.prereq_state = {prereq_name: None for prereq_name in prereq_names}

        def check(self):
            # update prereq state first
            for prereq_name, prereq_func in self.prereq_funcs.items():
                cur_value = self.prereq_state[prereq_name]
                new_value = prereq_func(cur_value)
                if cur_value != new_value:
                    self.logger.debug("{} changed from {} to {}", prereq_name, cur_value, new_value)
                    self.prereq_state[prereq_name] = new_value

            # then the actual cond checks
            for cond_group_idx, cond_group in enumerate(self.cond_groups):
                cond_group_result = self._check_cond_group(cond_group_idx, cond_group)
                if cond_group_result: # ANY cond group must evaluate to be truthy
                    raise AbortConditionsSatisfied(cond_group_result)

        def _check_cond_group(self, cond_group_idx, cond_group):
            cond_results = []
            for raw_cond, cond_func in cond_group:
                cond_result = cond_func(**self.prereq_state)
                self.logger.trace("abort condition [group {}] {}(**{!r}) => {}",
                    cond_group_idx, raw_cond, self.prereq_state, cond_result)
                if not cond_result: # ALL conditions in a group must evaluate to be truthy
                    return None
                cond_results.append(cond_result)
            return ' AND '.join(cond_results) or None

    @loggingutils.contextdecorator
    def _log_with_video_id(self, video_id, *args, **kwargs):
        cls_logger = loggingutils.getLogger(self.__class__.logger) # ensure we get the Logger and not a LoggerAdapter
        self.logger = loggingutils.FormatLoggerAdapter(cls_logger, style='{', extra={'context': f"[{kwargs.get('log_base_context', '')}{video_id}]"})
        try:
            yield
        finally:
            del self.logger

    @_log_with_video_id
    def get_youtube_messages(self, video_id, start_time=0, end_time=None, message_type='messages', chat_type='live', callback=None, output_messages=None, **kwargs):
        """ Get chat messages for a YouTube video. """

        start_time = self.__ensure_seconds(start_time, 0)
        end_time = self.__ensure_seconds(end_time, None)
        self.logger.trace("kwargs: {}", kwargs)
        abort_cond_groups = kwargs.get('abort_condition')

        messages = [] if output_messages is None else output_messages

        offset_milliseconds = start_time * 1000 if start_time > 0 else 0

        # Top chat replay - Some messages, such as potential spam, may not be visible
        # Live chat replay - All messages are visible
        chat_type_field = chat_type.title()
        chat_replay_field = '{} chat replay'.format(chat_type_field)
        chat_live_field = '{} chat'.format(chat_type_field)

        try:
            abort_cond_checker = None
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
                        if abort_cond_groups:
                            if abort_cond_checker is None:
                                abort_cond_checker = self.AbortConditionChecker(self.logger, abort_cond_groups,
                                    orig_scheduled_start_time=lambda _: config.get('scheduled_start_time'),
                                    curr_scheduled_start_time=lambda _: config.get('scheduled_start_time'))
                            abort_cond_checker.check()

                        retry_wait_secs = random.randint(30, 45) # jitter
                        self.logger.debug("Upcoming {} Retrying in {} secs (attempt {})", error_message, retry_wait_secs, attempt_ct)
                        time.sleep(retry_wait_secs)
                    else:
                        raise NoChatReplay(error_message)
                else:
                    if self.logger.isEnabledFor(logging.DEBUG): # guard since json.dumps is expensive
                        self.logger.debug("config:\n{}", _debug_dump(config))
                        self.logger.debug("continuation_by_title_map:\n{}", _debug_dump(continuation_by_title_map))
                    break
            continuation = continuation_by_title_map[continuation_title]

            abort_cond_checker = None
            first_time = True
            while True:
                if abort_cond_groups:
                    if abort_cond_checker is None:
                        scheduled_start_time_poll_timestamp = None
                        def scheduled_start_time_getter(curr_scheduled_start_time):
                            nonlocal scheduled_start_time_poll_timestamp
                            # if first call, init with config scheduled_start_time
                            if scheduled_start_time_poll_timestamp is None:
                                scheduled_start_time_poll_timestamp = time.time()
                                return config.get('scheduled_start_time')
                            # assume that curr_scheduled_start_time is None when video stream has started (is no longer upcoming)
                            if curr_scheduled_start_time is None:
                                return None
                            now_timestamp = time.time()
                            if now_timestamp > scheduled_start_time_poll_timestamp + 60: # check at most once a minute
                                scheduled_start_time_poll_timestamp = now_timestamp
                                return self.__get_scheduled_start_time(self.__get_heartbeat_info(video_id, config))
                            else:
                                return curr_scheduled_start_time
                        abort_cond_checker = self.AbortConditionChecker(self.logger, abort_cond_groups,
                            orig_scheduled_start_time=lambda _: config.get('scheduled_start_time'),
                            curr_scheduled_start_time=scheduled_start_time_getter)
                    abort_cond_checker.check()

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

        except AbortConditionsSatisfied as e:
            print('[Abort conditions satisfied]', e, flush=True)
            return messages
        except KeyboardInterrupt:
            print('[Interrupted]', flush=True)
            return messages

    @_log_with_video_id
    def get_twitch_messages(self, video_id, start_time=0, end_time=None, callback=None, output_messages=None, **kwargs):
        start_time = self.__ensure_seconds(start_time, 0)
        end_time = self.__ensure_seconds(end_time, None)

        messages = [] if output_messages is None else output_messages

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

    def get_chat_replay(self, url, start_time=0, end_time=None, message_type='messages', chat_type='live', callback=None, output_messages=None, **kwargs):
        match = re.search(self.__YT_REGEX, url)
        if(match):
            return self.get_youtube_messages(match.group(1), start_time, end_time, message_type, chat_type, callback, output_messages, **kwargs)

        match = re.search(self.__TWITCH_REGEX, url)
        if(match):
            return self.get_twitch_messages(match.group(1), start_time, end_time, callback, output_messages, **kwargs)

        raise InvalidURL('The url provided ({}) is invalid.'.format(url))


def get_chat_replay(url, start_time=0, end_time=None, message_type='messages', chat_type='live', callback=None, output_messages=None, **kwargs):
    return ChatReplayDownloader().get_chat_replay(url, start_time, end_time, message_type, chat_type, callback, output_messages, **kwargs)

def get_youtube_messages(url, start_time=0, end_time=None, message_type='messages', chat_type='live', callback=None, output_messages=None, **kwargs):
    return ChatReplayDownloader().get_youtube_messages(url, start_time, end_time, message_type, chat_type, callback, output_messages, **kwargs)

def get_twitch_messages(url, start_time=0, end_time=None, callback=None, output_messages=None, **kwargs):
    return ChatReplayDownloader().get_twitch_messages(url, start_time, end_time, callback, output_messages, **kwargs)

def _debug_dump(obj):
    return json.dumps(obj, indent=4, default=str)

def main(args):
    parser = argparse.ArgumentParser(
        description='A simple tool used to retrieve YouTube/Twitch chat from past broadcasts/VODs. No authentication needed!',
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('url', help='YouTube/Twitch video URL')

    parser.add_argument('--start_time', '--from', default=0,
                        help='start time in seconds or hh:mm:ss\n(default: %(default)s)')
    parser.add_argument('--end_time', '--to', default=None,
                        help='end time in seconds or hh:mm:ss\n(default: %(default)s = until the end)')

    parser.add_argument('--message_type', choices=['messages', 'superchat', 'all'], default='messages',
                        help='types of messages to include [YouTube only]\n(default: %(default)s)')

    parser.add_argument('--chat_type', choices=['live', 'top'], default='live',
                        help='which chat to get messages from [YouTube only]\n(default: %(default)s)')

    parser.add_argument('--output', '-o', default=None,
                        help='name of output file\n(default: %(default)s = print to standard output)')

    parser.add_argument('--cookies', '-c', default=None,
                        help='name of cookies file\n(default: %(default)s)')

    abort_cond_action = parser.add_argument('--abort_condition', action='append',
                        type=lambda raw_cond_group: ChatReplayDownloader.parse_abort_condition_group(raw_cond_group,
                                                        lambda msg: argparse.ArgumentError(abort_cond_action, msg)),
                        help="a condition on which this application aborts (note: ctrl+c is such a condition by default)\n"
                             "Available conditions for upcoming streams:\n"
                             "* changed_scheduled_start_time:<strftime format e.g. %%Y%%m%%d> [YouTube-only]\n"
                             "  True if datetime.strftime(<strftime format>) changes between initially fetched scheduled start datetime.\n"
                             "  and latest fetched scheduled start datetime.\n"
                             "* min_time_until_scheduled_start_time:<hours>:<minutes> [YouTube-only]\n"
                             "  True if (latest fetched scheduled start datetime - current datetime) >= timedelta(hours=<hours>, minutes=<minutes>).\n"
                             "Multiple abort conditions can be specified within a single --abort_condition option,\n"
                             "delimited by + (whitespace allowed before and after, though the whole argument may need to be quoted then),\n"
                             "and such abort conditions are ANDed together as a 'condition group'.\n"
                             "In case a condition argument itself must contain +, + can be escaped as \\+ (and \\ can be escaped as \\\\).\n"
                             "Multiple --abort_condition options can be specified, and the condition groups represented by each option are ORed together.\n"
                             "Example:\n"
                             "  --abort_condition 'changed_scheduled_start_time:%%Y%%m%%d + min_time_until_scheduled_start_time:00:10'\n"
                             "  --abort_condition min_time_until_scheduled_start_time:24:00\n"
                             "means abort if:\n"
                             "  (both scheduled start datetime changes date AND current time until scheduled start datetime is at least 10 minutes)\n"
                             "  OR current time until scheduled start datetime is at least 24 hours\n"
                             "Any combination of ORs and ANDs can be represented by this system, since abort conditions are effectively a boolean formula,\n"
                             "and any boolean formula can be converted into this OR of ANDs form (a.k.a. disjunctive normal form).")

    parser.add_argument('--hide_output', action='store_true',
                        help='whether to hide stdout and stderr output or not\n(default: %(default)s)')

    parser.add_argument('--log_file', action='append',
                        help="file (or console) to log output to, including redirecting stdout and stderr to it\n"
                            "(default: :console:)\n"
                            "If --hide_output is true, this option has no effect.\n"
                            "If specified and not ':console:', redirects stdout and stderr to the given log file.\n"
                            "If specified as ':console:', outputs stdout and stderr to console as normal.\n"
                            "Multiple --log_file options can be specified, allowing output to multiple log files and/or console.")

    parser.add_argument('--log_level',
                        choices=[name for level, name in logging._levelToName.items() if level != 0],
                        default=logging._levelToName[logging.WARNING],
                        help='log level, logged to standard output\n(default: %(default)s)')

    parser.add_argument('--log_base_context', default='',
                        help='lines logged to standard output are formatted as:\n'
                             '"[<log_level>][<datetime>][<log_base_context><video_id>] <message>" (without the quotes)\n'
                             "(default: '%(default)s')")

    # preprocess any long-form '-' args into '--' args
    args = ['-' + arg if len(arg) >= 3 and arg[0] == '-' and arg[1] != '-' else arg for arg in args]

    args = parser.parse_args(args)

    # set encoding of standard output and standard error to utf-8
    orig_stdout_encoding = sys.stdout.encoding
    if orig_stdout_encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    orig_stderr_encoding = sys.stderr.encoding
    if orig_stderr_encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')

    if args.hide_output:
        log_files = [open(os.devnull, 'w')]
    elif args.log_file:
        log_files = [open(log_file, 'w') if log_file != ':console:' else None for log_file in args.log_file]
    else:
        log_files = [None] # effectively ':console:'
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr
    out_log_files = [log_file if log_file else sys.stdout for log_file in log_files]
    err_log_files = [log_file if log_file else sys.stderr for log_file in log_files]
    if len(log_files) == 1:
        sys.stdout = out_log_files[0]
        sys.stderr = err_log_files[0]
    else:
        sys.stdout = ioutils.MultiFile(*out_log_files)
        sys.stderr = ioutils.MultiFile(*err_log_files)

    # this has to go after stdout/stderr are modified
    logging.basicConfig(force=True, level=args.log_level, stream=sys.stdout,
                        format='[%(levelname)s][%(asctime)s][%(name)s] %(message)s', datefmt=ChatReplayDownloader.DATETIME_FORMAT)

    num_of_messages = 0
    chat_messages = []

    orig_signal_handlers = {}
    called_finalize_output=False
    def finalize_output(signum=None, frame=None):
        if signum:
            name = signal.Signals(signum).name # pylint: disable=no-member # pylint lies - signal.Signals does exist
            print(f"[{'Signal Received: ' + name[3:].capitalize() if name.startswith('SIG') else name.capitalize()}]", flush=True)

        nonlocal called_finalize_output
        if called_finalize_output:
            return
        else:
            called_finalize_output = True

        nonlocal num_of_messages
        try:
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
        finally:
            try:
                for orig_signum, orig_handler in orig_signal_handlers.items():
                    signal.signal(orig_signum, orig_handler)
                for log_file in log_files:
                    if log_file: # if an actual file (not sys.__stdout__ or sys.__stderr__)
                        #print(f"Closing {log_file}", flush=True)
                        log_file.close()
                sys.stdout = orig_stdout
                sys.stderr = orig_stderr
                if orig_stdout_encoding != 'utf-8':
                    sys.stdout.reconfigure(encoding=orig_stdout_encoding)
                if orig_stderr_encoding != 'utf-8':
                    sys.stderr.reconfigure(encoding=orig_stderr_encoding)
            finally:
                if signum:
                    sys.exit()

    FINALIZE_OUTPUT_SIGNAL_NAMES = (
        # 'SIGINT', # SIGINT is handled by catching KeyboardInterrupt
        'SIGBREAK', # Windows-only - allow ctrl-break to gracefully exit (sometimes ctrl+c won't work)
        'SIGQUIT', # Unix-only
        'SIGTERM',
        'SIGABRT',
    )
    for signal_name in FINALIZE_OUTPUT_SIGNAL_NAMES:
        signum = getattr(signal, signal_name, None)
        if signum:
            orig_signal_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, finalize_output)

    try:
        chat_downloader = ChatReplayDownloader(cookies=args.cookies)

        def print_item(item):
            chat_downloader.print_item(item)

        def write_to_file(item):
            nonlocal num_of_messages

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
                pass
            else:
                open(args.output, 'w').close()  # empty the file
                callback = write_to_file

        # using output_messages arg rather than return value, in case of uncaught exception or caught signal within the call
        chat_downloader.get_chat_replay(callback=callback, output_messages=chat_messages, **vars(args))

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
    except KeyboardInterrupt: # this should already be caught within get_chat_replay, but keeping this just in case
        print('[Interrupted]', flush=True)
    except SystemExit: # finalize_output may call sys.exit() which raises SystemExit
        pass # in case main() is being called from another module, don't actually exit the app
    except Exception:
        # print full stack trace (rather than only up to main(), the containing method)
        import traceback
        stacklines = traceback.format_exc().splitlines(keepends=True)
        stacklines[1:1] = traceback.format_list(traceback.extract_stack()[:-1])
        print(''.join(stacklines), end='', file=sys.stderr)
    finally:
        finalize_output()

if __name__ == '__main__':
    main(sys.argv[1:])
