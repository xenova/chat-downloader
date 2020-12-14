#!/usr/bin/env python3
import requests
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
import sqlite3
import collections.abc
from typing import List, Optional, Dict


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


class DBInvalidState(Exception):
    """Raised when DBChat instance is in invalid state"""
    pass


class DBChat(object):
    """DBChat: wrapper for sqlite3 connection

    First create instance providing path which is usually a file location.
    Second call create_session with url and other params to create session.
    Then can call add_item to add a record
    When finished can call finish_session to mark the session completed"""

    def __init__(self, path: str, autoInit: bool = True) -> None:
        """path is file location, None to make DBChat perform no op, use ':memory:' for in memory"""
        self.path: str = path
        self.noOp: bool = False
        self.dbConn: sqlite3.Connection = sqlite3.connect(
            path, isolation_level="IMMEDIATE")
        self.session_id: Optional[int] = None
        if(autoInit):  # auto create data table and make connections
            self.init_db()

    def init_db(self) -> List[str]:
        """will create table session and chat_detail if thoese two table not exists"""
        if(self.noOp):
            return []
        result: List[str] = []
        cur: sqlite3.Cursor = self.dbConn.cursor()
        try:
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", ('session',))
            rows: List[sqlite3.Row] = cur.fetchall()
            if(len(rows) == 0):
                # then init the database with session table
                cur.execute("""CREATE TABLE session(
                    id INTEGER PRIMARY KEY ASC, /* id, insert with no id will autoincrease */
                    url TEXT NOT NULL, /* url for target */
                    record_time TEXT, /* time, in ISO-8601 string */
                    completed INTEGER DEFAULT 0, /* if complete record all chats, set to 1 */
                    start_time INTEGER, /* start_time parameter, in seconds relative to video begin */
                    end_time INTEGER, /* end_time parameter, in seconds relative to video begin */
                    message_type TEXT, /* message_type(youtube only), one of 'superchat' / 'all' / 'messages' */
                    chat_type TEXT /* chat_type(youtube only), one of 'top', 'live' */
                )""")
                result.append("session")
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", ('chat_detail',))
            rows = cur.fetchall()
            if(len(rows) == 0):
                # then init the database with chat_detail table
                cur.execute("""CREATE TABLE chat_detail(
                    id INTEGER PRIMARY KEY ASC, /* should insert with no id to autoincrease */
                    session_id INTEGER NOT NULL, /* associate with session.id */
                    time_text TEXT, /* time of chat in ISO format */
                    timestamp INTEGER, /* time of chat in Unix time in microseconds */
                    badges TEXT, /* badges for user identity, like 'New member' or 'Moderator, Member (1 year, 4 months)' */
                    author TEXT, /* author name */
                    author_id TEXT, /* author_id that unique identify a user */
                    message TEXT, /* the message of chat */
                    sc_amount TEXT, /* amount of money in sc chat, not integer because contains corrency marks */
                    head_color TEXT, /* in format "{'rgba': [255, 202, 40, 255], 'hex': '#ffca28ff'}" */
                    body_color TEXT, /* same format as head_color */
                    ticker_duration INTEGER, /* duration of superchat visible, in seconds */
                    FOREIGN KEY (session_id) REFERENCES session (id)
                )""")
                # cur.execute(
                #     "CREATE INDEX IF NOT EXISTS idx_session_id ON chat_detail(session_id)")
                result.append("chat_detail")
            self.dbConn.commit()
            return result
        finally:
            cur.close()

    def create_session(self, url: str, start_time : int, end_time: int, message_type : str = None, chat_type : str =None) -> Optional[int]:
        """will create a session and return the session id to be used in chat_detail table.
        Also the self.session_id will be set. Must call this before insert value

        url: str --- the url for the session"""
        if(self.noOp):
            return None  # no op will do nothing
        if(self.session_id is not None):
            return self.session_id  # not create second time
        if(url == None):
            raise TypeError("url should not be None")
        if(self.dbConn is None):
            raise DBInvalidState("database already closed or failed init")
        try:
            cur = self.dbConn.cursor()
            now: datetime.datetime = datetime.datetime.now()
            cur.execute(
                "INSERT INTO session(url, record_time, completed, start_time, end_time, message_type, chat_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (url, now, 0, start_time, end_time, message_type, chat_type))
            self.session_id = cur.lastrowid
            self.dbConn.commit()
            print("start new session, session_id:", self.session_id)
        finally:
            cur.close()
        return self.session_id

    def add_item(self, item: Dict[str, str]) -> Optional[int]:
        """Add an item record into chat_detail.
        Notice: must call create_session once before call this method to init session,
        otherwise will raise an exception

        item: the same as the only argument in callback, an dict with 'author' 'message' fields and so on"""
        if(self.noOp):
            return None
        if(self.session_id is None):
            raise DBInvalidState("must call create_session before add_item")
        cur = self.dbConn.cursor()

        def fi(key: str):
            """fi fetch key in item and return None if not found or find '' string,
            and also convert other type into sqlite3 capable basic type,
            also will try to extract the hex color value if found"""
            if(key not in item or item[key] is None):
                return None
            if(item[key] == ''):
                item[key] = None
                return None
            # None will convert to Null in sqlite3
            obj = item[key]
            # datetime and date can auto convert to string if inserted
            if(isinstance(obj, (datetime.datetime, datetime.date))):
                return obj
            # other accepted type is those four
            if(isinstance(obj, (int, float, str, bytes))):
                return obj
            # bool should transform into 0 / 1
            if(obj is True):
                return 1
            if(obj is False):
                return 0
            # if the current object is dict and contains both hex and rgba, means it is color dict
            if(isinstance(obj, collections.abc.Mapping) and 'hex' in obj and 'rgba' in obj and isinstance(obj['hex'], str)):
                return obj['hex']
            return json.dumps(obj)

        try:
            if(fi('time_text') is None and fi('timestamp') is not None):
                # fill in the 'time_text' from 'timestamp' if is None
                item['time_text'] = datetime.datetime.fromtimestamp(
                    item['timestamp'] // 1000000).isoformat()
                # note: timestamp's unit is microseconds, need to convert to second
            cur.execute("""INSERT INTO chat_detail(
                session_id, time_text, timestamp, 
                badges, author, author_id, message, 
                sc_amount, head_color, body_color, ticker_duration)
                VALUES (?, ?, ?,   ?, ?, ?, ?,   ?, ?, ?, ?)""",
                        (self.session_id, fi('time_text'), fi('timestamp'),
                         fi('badges'), fi('author'), fi(
                             'author_id'), fi('message'),
                         fi('amount'), fi('head_color'), fi('body_color'), fi('ticker_duration')))
            result: int = cur.lastrowid
            self.dbConn.commit()
            return result
        finally:
            cur.close()

    def finish_session(self) -> None:
        """close current session and update session table to set completed = 1"""
        if(self.noOp or self.session_id is None):
            return
        cur = self.dbConn.cursor()
        try:
            cur.execute(
                "UPDATE session SET completed = 1 WHERE id = ?", (self.session_id,))
            self.dbConn.commit()
        finally:
            cur.close()
            self.session_id = None
            self.noOp = True


class ChatReplayDownloader:
    """A simple tool used to retrieve YouTube/Twitch chat from past broadcasts/VODs. No authentication needed!"""

    __HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36',
        'Accept-Language': 'en-US, en'
    }

    __YT_HOME = 'https://www.youtube.com'
    __YT_REGEX = r'(?:/|%3D|v=|vi=)([0-9A-z-_]{11})(?:[%#?&]|$)'
    __YOUTUBE_API_BASE_TEMPLATE = '{}/{}/{}?continuation={}&pbj=1&hidden=false'
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

        # set the place for chat_db
        self.chat_db: Optional[DBChat] = None

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
        """
        Format item for printing to standard output.
        [time] (badges) *money* author: message,
        where (badges) and *money* are optional.
        """
        return '[{}] {}{}{}: {}'.format(
            item['time_text'] if 'time_text' in item else (
                self.__microseconds_to_timestamp(item['timestamp']) if 'timestamp' in item else ''),
            '({}) '.format(item['badges']) if 'badges' in item else '',
            '*{}* '.format(item['amount']) if 'amount' in item else '',

            item.get('author', ''),
            item.get('message', '')
        )

    def print_item(self, item):
        """
        Ensure printing to standard output can be done safely (especially on Windows).
        There are usually issues with printing emojis and non utf-8 characters.
        """
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
        if(text.startswith('/redirect')):  # is a redirect link
            info = dict(parse.parse_qsl(parse.urlsplit(text).query))
            return info['q'] if 'q' in info else ''
        elif(text.startswith('/watch')):  # is a youtube video link
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
                raise ValueError('Unknown run: {}'.format(run))

        return message_text

    _YT_INITIAL_DATA_RE = r'(?:window\s*\[\s*["\']ytInitialData["\']\s*\]|ytInitialData)\s*=\s*({.+?})\s*;'

    def __get_initial_youtube_info(self, video_id):
        """ Get initial YouTube video information. """
        original_url = '{}/watch?v={}'.format(self.__YT_HOME, video_id)
        html = self.__session_get(original_url)

        info = re.search(self._YT_INITIAL_DATA_RE, html.text)

        if(not info):
            raise ParsingError(
                'Unable to parse video data. Please try again.')

        ytInitialData = json.loads(info.group(1))
        # print(ytInitialData)
        contents = ytInitialData.get('contents')
        if(not contents):
            raise VideoUnavailable('Video is unavailable (may be private).')

        columns = contents.get('twoColumnWatchNextResults')

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
        url = self.__YOUTUBE_API_BASE_TEMPLATE.format(self.__YT_HOME,
                                                      'live_chat_replay', 'get_live_chat_replay', continuation) + self.__YOUTUBE_API_PARAMETERS_TEMPLATE.format(offset_microseconds)
        return self.__get_continuation_info(url)

    def __get_live_info(self, continuation):
        """Get YouTube live info, given a continuation."""
        url = self.__YOUTUBE_API_BASE_TEMPLATE.format(self.__YT_HOME,
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

        if('time_text' in data):
            data['time_in_seconds'] = int(
                self.__time_to_seconds(data['time_text']))

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

        # start the new session for chat_db
        if(self.chat_db is not None):
            self.chat_db.create_session(
                self.__YT_HOME + '/watch?v=' + video_id, start_time, end_time, message_type, chat_type)

        first_time = True
        try:
            while True:
                try:
                    if(is_live):
                        info = self.__get_live_info(continuation)
                    else:
                        # must run to get first few messages, otherwise might miss some
                        if(first_time):
                            info = self.__get_replay_info(continuation, 0)
                            first_time = False
                        else:
                            info = self.__get_replay_info(
                                continuation, offset_milliseconds)

                except NoContinuation:
                    print('No continuation found, stream may have ended.')
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
                        elif(message_type != 'superchat' and index in self.__TYPES_OF_MESSAGES['superchat_message'] + self.__TYPES_OF_MESSAGES['superchat_ticker']):
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
                            if(self.chat_db is not None):
                                # add date to sqlite db
                                self.chat_db.add_item(data)
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
                        time.sleep(continuation_info['timeoutMs']/1000)
                else:
                    break

            if(self.chat_db is not None):
                # finish a session here
                self.chat_db.finish_session()
            return messages

        except KeyboardInterrupt:
            if(self.chat_db is not None):
                self.chat_db.finish_session()
            return messages

    def get_twitch_messages(self, video_id, start_time=0, end_time=None, callback=None):
        start_time = self.__ensure_seconds(start_time, 0)
        end_time = self.__ensure_seconds(end_time, None)

        messages = []
        api_url = self.__TWITCH_API_TEMPLATE.format(
            video_id, self.__TWITCH_CLIENT_ID)

        if(self.chat_db is not None):
            self.chat_db.create_session(
                'https://www.twitch.tv/videos/' + video_id, start_time, end_time)

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

                    if(self.chat_db is not None):
                        self.chat_db.add_item(data)

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
                    if(self.chat_db is not None):
                        self.chat_db.finish_session()
                    return messages
        except KeyboardInterrupt:
            if(self.chat_db is not None):
                self.chat_db.finish_session()
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

    parser.add_argument('--hide_output', action='store_true',
                        help='whether to hide output or not\n(default: %(default)s)')

    parser.add_argument('-database', '-db', default='chat_data.db',
                        help='database to hold chat data\n(default: %(default)s)')

    args = parser.parse_args()

    if(args.hide_output):
        f = open(os.devnull, 'w')
        sys.stdout = f
        sys.stderr = f
    else:
        # set encoding of standard output and standard error
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

    try:
        chat_downloader = ChatReplayDownloader(cookies=args.cookies)

        # setup the database
        chat_downloader.chat_db = DBChat(args.database)

        num_of_messages = 0

        def print_item(item):
            chat_downloader.print_item(item)

        def write_to_file(item):
            global num_of_messages

            # only file format capable of appending properly
            with open(args.output, 'a', encoding='utf-8') as f:
                if('ticker_duration' not in item):  # needed for duplicates
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

        chat_messages = chat_downloader.get_chat_replay(
            args.url,
            start_time=args.start_time,
            end_time=args.end_time,
            message_type=args.message_type,
            chat_type=args.chat_type,
            callback=callback
        )

        # close the database and remove reference
        if(chat_downloader.chat_db is not None and chat_downloader.chat_db.dbConn is not None):
            chat_downloader.chat_db.dbConn.close()
            chat_downloader.chat_db.dbConn = None
            chat_downloader.chat_db = None

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
                fieldnames.sort()

                with open(args.output, 'w', newline='', encoding='utf-8') as f:
                    fc = csv.DictWriter(f, fieldnames=fieldnames)
                    fc.writeheader()
                    fc.writerows(chat_messages)

            print('Finished writing', num_of_messages,
                  'messages to', args.output, flush=True)

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
