
from .common import ChatDownloader

from ..utils import microseconds_to_timestamp

from ..errors import * # only import used

from urllib import parse

import json
#import bs4
import time
import re
import emoji

from ..utils import (
    try_get,
    time_to_seconds,
    int_or_none
    )

class YouTubeChatDownloader(ChatDownloader):
    def __init__(self, updated_init_params = {}):
        super().__init__(updated_init_params)

    # Regex provided by youtube-dl
    _VALID_URL = r"""(?x)^
                     (
                         (?:https?://|//)                                    # http(s):// or protocol-independent URL
                         (?:(?:(?:(?:\w+\.)?[yY][oO][uU][tT][uU][bB][eE](?:-nocookie|kids)?\.com/|
                            youtube\.googleapis\.com/)                        # the various hostnames, with wildcard subdomains
                         (?:.*?\#/)?                                          # handle anchor (#/) redirect urls
                         (?:                                                  # the various things that can precede the ID:
                             (?:(?:v|embed|e)/(?!videoseries))                # v/ or embed/ or e/
                             |(?:                                             # or the v= param in all its forms
                                 (?:(?:watch|movie)(?:_popup)?(?:\.php)?/?)?  # preceding watch(_popup|.php) or nothing (like /?v=xxxx)
                                 (?:\?|\#!?)                                  # the params delimiter ? or # or #!
                                 (?:.*?[&;])??                                # any other preceding param (like /?s=tuff&v=xxxx or ?s=tuff&amp;v=V36LpHqtcDY)
                                 v=
                             )
                         ))
                         |(?:
                            youtu\.be|                                        # just youtu.be/xxxx
                         ))
                     )?                                                       # all until now is optional -> you can pass the naked ID
                     (?P<id>[0-9A-Za-z_-]{11})                                      # here is it! the YouTube video ID
                     $"""

    _YT_INITIAL_DATA_RE = r'(?:window\s*\[\s*["\']ytInitialData["\']\s*\]|ytInitialData)\s*=\s*({.+?})\s*;'


    _YT_HOME = 'https://www.youtube.com'
    #__YT_REGEX = r'(?:/|%3D|v=|vi=)([0-9A-z-_]{11})(?:[%#?&]|$)'
    _YOUTUBE_API_BASE_TEMPLATE = '{}/{}/{}?continuation={}&pbj=1&hidden=false'
    _YOUTUBE_API_PARAMETERS_TEMPLATE = '&playerOffsetMs={}'

    _TYPES_OF_MESSAGES = {
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

    _IMPORTANT_KEYS_AND_REMAPPINGS = {
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

    _MESSAGE_FORMATTING_GROUPS_REGEX = r'\{(.*?)\{(.*?)?\}(.*?)\}'
    _MESSAGE_FORMATTING_INDEXES_REGEX = r'\|(?![^\[]*\])'
    _MESSAGE_FORMATTING_FORMATTING_REGEX = r'(.*)\[(.*)\]'


    # liveChatAuthorBadgeRenderer
    def _camel_case_split(self, word):
        return '_'.join(re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', word)).lower()

    def _strip_live_chat_renderer(self, index):

        if index.startswith('liveChat'): # remove prefix
            index = index[8:]
        if index.endswith('Renderer'): # remove suffix
            index = index[0:-8:]

        return index

# "addChatItemAction":{
#     "item":{
#         "liveChatViewerEngagementMessageRenderer":{
    def _parse_live_chat_item(self, item):
        info = {}

        try:
            item_index = next(iter(item))
        except:
            return info # invalid # TODO log this

        item_info = item.get(item_index)

        if(not item_info):
            return info

        # all messages should have the following
        info['index'] = self._camel_case_split(self._strip_live_chat_renderer(item_index))
        info['id'] = item_info.get('id')



        return info


            # 'liveChatViewerEngagementMessageRenderer',
            # 'liveChatPurchasedProductMessageRenderer',  # product purchased
            # 'liveChatPlaceholderItemRenderer',  # placeholder
            # 'liveChatModeChangeMessageRenderer'  # e.g. slow mode enabled
			# 'liveChatTextMessageRenderer'  # normal message
			# 'liveChatMembershipItemRenderer',
            # 'liveChatPaidMessageRenderer',
            # 'liveChatPaidStickerRenderer',
			# 'liveChatTickerPaidStickerItemRenderer',
            # 'liveChatTickerPaidMessageItemRenderer',
            # 'liveChatTickerSponsorItemRenderer',









    def _parse_youtube_link(self, text):
        if(text.startswith('/redirect')):  # is a redirect link
            info = dict(parse.parse_qsl(parse.urlsplit(text).query))
            return info['q'] if 'q' in info else ''
        elif(text.startswith('/watch')):  # is a youtube video link
            return self._YT_HOME + text
        else:  # is a normal link
            return text

    def _parse_message_runs(self, runs):
        """ Reads and parses YouTube formatted messages (i.e. runs). """
        message_text = ''
        for run in runs:
            if 'text' in run:
                if 'navigationEndpoint' in run:  # is a link
                    try:
                        url = run['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url']
                        message_text += self._parse_youtube_link(url)
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

    def _get_initial_info(self, video_id):
        """ Get initial YouTube video information. """
        original_url = '{}/watch?v={}'.format(self._YT_HOME, video_id)
        html = self._session_get(original_url)

        info = re.search(self._YT_INITIAL_DATA_RE, html.text)

        if(not info):
            raise ParsingError(
                    'Unable to parse video data. Please try again.')

        ytInitialData = json.loads(info.group(1))

        #print()
        #soup = bs4.BeautifulSoup(html, 'html.parser')




        # ytInitialData_script = next(script.string for script in soup.find_all(
        #     'script') if script.string and 'ytInitialData' in script.string)

        # print(ytInitialData_script)

        # json_data = next(line.strip()[len('window["ytInitialData"] = '):-1]
        #                  for line in ytInitialData_script.splitlines() if 'ytInitialData' in line)
        # return
        # try:

        # except Exception as e:
        #     print("ERROR")
        #     #print(json_data)
        #     try:
        #         # for some reason, it sometimes cuts out and this fixes it
        #         ytInitialData = json.loads('{"resp'+json_data)
        #         # TODO print out and see why this happens...
        #         # regex bad?
        #     except Exception:

        contents = ytInitialData.get('contents')
        if(not contents):
            raise VideoUnavailable('Video is unavailable (may be private).')

        columns = contents.get('twoColumnWatchNextResults')

        if('conversationBar' not in columns or 'liveChatRenderer' not in columns['conversationBar']):
            error_message = 'Video does not have a chat replay.'
            try:
                error_message = self._parse_message_runs(
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

    def _get_replay_info(self, continuation, offset_microseconds = None):
        """Get YouTube replay info, given a continuation or a certain offset."""
        url = self._YOUTUBE_API_BASE_TEMPLATE.format(self._YT_HOME,
                                                      'live_chat_replay', 'get_live_chat_replay', continuation)
        if(offset_microseconds is not None):
            url += self._YOUTUBE_API_PARAMETERS_TEMPLATE.format(offset_microseconds)

        return self._get_continuation_info(url)

    def _get_live_info(self, continuation):
        """Get YouTube live info, given a continuation."""
        url = self._YOUTUBE_API_BASE_TEMPLATE.format(self._YT_HOME,
                                                      'live_chat', 'get_live_chat', continuation)
        return(self._get_continuation_info(url))

    def _get_continuation_info(self, url):
        """Get continuation info for a YouTube video."""
        info = self._session_get_json(url)
        if('continuationContents' in info['response']):
            return info['response']['continuationContents']['liveChatContinuation']
        else:
            raise NoContinuation

    # TODO move to utils
    def _ensure_seconds(self, time, default=None):
        """Ensure time is returned in seconds."""
        if(not time): # if empty, return default
            return default

        try:
            return int(time)
        except ValueError:
            return time_to_seconds(time)
        except:
            return default

    def _parse_item(self, item):
        """Parse YouTube item information."""
        data = {}
        item_info = next(iter(item.values()))

        important_item_info = {key: value for key, value in item_info.items(
        ) if key in self._IMPORTANT_KEYS_AND_REMAPPINGS}

        data.update(important_item_info)

        for key in important_item_info:
            new_key = self._IMPORTANT_KEYS_AND_REMAPPINGS[key]
            data[new_key] = data.pop(key)

            # get simpleText if it exists
            if(type(data[new_key]) is dict and 'simpleText' in data[new_key]):
                data[new_key] = data[new_key]['simpleText']

        author_badges = item_info.get('authorBadges')
        if(author_badges):

            data['badges'] = []
            for badge in author_badges:
                b = try_get(badge, lambda x: x['liveChatAuthorBadgeRenderer']['tooltip'])
                if(b):
                    data['badges'].append(b)
                #if('liveChatAuthorBadgeRenderer' in badge and 'tooltip' in badge['liveChatAuthorBadgeRenderer']):

            #data['badges'] = badges# ', '.join()

        item_endpoint = item_info.get('showItemEndpoint')
        if(item_endpoint):  # has additional information
            data.update(self._parse_item(
                item_endpoint['showLiveChatItemEndpoint']['renderer']))
            return data

        data['message'] = self._parse_message_runs(
            data['message']['runs']) if 'message' in data else None


        data['timestamp'] = int_or_none(data['timestamp'])

        if('time_text' in data):
            data['time_in_seconds'] = time_to_seconds(data['time_text'])

        for colour_key in ('header_color', 'body_color'):
            if(colour_key in data):
                data[colour_key] = self._get_colours(data[colour_key])

        return data


    def _format_item(self, result, item):

        # split by | not enclosed in []
        split = re.split(self._MESSAGE_FORMATTING_INDEXES_REGEX,result.group(2))
        for s in split:

            # check if optional formatting is there
            parse = re.search(self._MESSAGE_FORMATTING_FORMATTING_REGEX, s)
            formatting = None
            if(parse):
                index = parse.group(1)
                formatting = parse.group(2)
            else:
                index = s

            if(index in item):
                value = item[index]
                if(formatting):
                    if(index == 'timestamp'):
                        value = microseconds_to_timestamp(item[index],format=formatting)
                    # possibility for more formatting options

                    # return value if index matches, otherwise keep searching
                return '{}{}{}'.format(result.group(1), value, result.group(3))

        return '' # no match, return empty

    def message_to_string(self, item, format_string='{[{time_text|timestamp[%Y-%m-%d %H:%M:%S]}]}{ ({badges})}{ *{amount}*}{ {author}}:{ {message}}'):
        """
        Format item for printing to standard output. The default format_string will print out as:
        [time] (badges) *amount* author: message\n
        where (badges) and *amount* are optional.
        """


        return re.sub(self._MESSAGE_FORMATTING_GROUPS_REGEX, lambda result: self._format_item(result, item), format_string)
            # return '[{}] {}{}{}: {}'.format(
            # 	item['time_text'] if 'time_text' in item else (
            # 		self.__microseconds_to_timestamp(item['timestamp']) if 'timestamp' in item else ''),
            # 	'({}) '.format(item['badges']) if 'badges' in item else '',
            # 	'*{}* '.format(item['amount']) if 'amount' in item else '',
            # 	item['author'],
            # 	item['message'] or ''
            # )

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


        #'message_type':'messages'

       # =0, , , chat_type='live',
    #_DEFAULT_PARAMS



    # def parse_action(self, params, action):



    def get_chat_by_video_id(self, video_id, params):
        """ Get chat messages for a YouTube video. """


        initial_info = self._get_initial_info(video_id)

        #print(initial_info)




        start_time = self._ensure_seconds(params.get('start_time'), None)
        end_time = self._ensure_seconds(params.get('end_time'), None)

        #messages = []



        # Top chat replay - Some messages, such as potential spam, may not be visible
        # Live chat replay - All messages are visible

        chat_type = params.get('chat_type','live')

        chat_type_field = chat_type.title()
        chat_replay_field = '{} chat replay'.format(chat_type_field)
        chat_live_field = '{} chat'.format(chat_type_field)

        if(chat_replay_field in initial_info):
            is_live = False
            continuation_title = chat_replay_field
        elif(chat_live_field in initial_info):
            is_live = True
            continuation_title = chat_live_field
        else:
            raise NoChatReplay('Video does not have a chat replay.')

        continuation = initial_info[continuation_title]
        offset_milliseconds = start_time * 1000 if isinstance(start_time,int) else None



        first_time = True
        while True:
            #try:
            # the following can raise NoContinuation error
            if(is_live):
                info = self._get_live_info(continuation)
            else:
                # must run to get first few messages, otherwise might miss some
                if(first_time):
                    info = self._get_replay_info(continuation)#, 0
                    first_time = False
                else:
                    info = self._get_replay_info(
                        continuation, offset_milliseconds)

            #except NoContinuation:
                # print('No continuation found, stream may have ended.')
                # break
            actions = info.get('actions')
            if(actions):
                for action in actions:
                    data = {}

                    replay_chat_item_action = action.get('replayChatItemAction')
                    if(replay_chat_item_action):
                        offset_time = replay_chat_item_action.get('videoOffsetTimeMsec')
                        if(offset_time):
                            data['video_offset_time_msec'] = int(offset_time)
                        action = replay_chat_item_action['actions'][0]

                    action_name = next(iter(action)) # TODO change to iter and next?

                    item = action[action_name].get('item')

                    if(not item):
                        # not a valid item to display (usually message deleted)
                        continue

                    index = next(iter(item))

                    if(index in self._TYPES_OF_MESSAGES['ignore']):
                        # can ignore message (not a chat message)
                        continue

                    message_type = params.get('message_type')

                    # user wants everything, keep going
                    if(message_type == 'all'):
                        pass

                    # user does not want superchat + message is superchat
                    elif(message_type != 'superchat' and index in self._TYPES_OF_MESSAGES['superchat_message'] + self._TYPES_OF_MESSAGES['superchat_ticker']):
                        continue

                    # user does not want normal messages + message is normal
                    elif(message_type != 'messages' and index in self._TYPES_OF_MESSAGES['message']):
                        continue

                    data = dict(self._parse_item(item), **data)


                    # check if must add this message
                    if(not is_live):
                        time_in_seconds = data.get('time_in_seconds')
                        if(time_in_seconds is None):
                            return # invalid time

                        not_after_start = start_time is not None and time_in_seconds < start_time
                        not_before_end = end_time is not None and time_in_seconds > end_time

                        if(not_after_start or not_before_end):
                            return

                    params.get('messages').append(data)

                    callback = params.get('callback')
                    if(not callback):
                        # print if it is not a ticker message (prevents duplicates)
                        if(index not in self._TYPES_OF_MESSAGES['superchat_ticker']):
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
                # otherwise, is live, so keep trying

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
                # no continuation, end
                break


    # override base method
    def get_chat_messages(self, params):
        super().get_chat_messages(params)

        url = params.get('url')
        messages = params.get('messages')



        match = re.search(self._VALID_URL, url)


        if(match):

            if(match.group('id')): # normal youtube video
                return self.get_chat_by_video_id(match.group('id'),params)


            else: # TODO add profile, etc.
                pass





