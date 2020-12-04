
from .common import ChatDownloader

from ..utils import microseconds_to_timestamp

from ..errors import *  # only import used TODO

from urllib import parse

import json
#import bs4
import time
import re
import emoji

from ..utils import (
    try_get,
    time_to_seconds,
    int_or_none,
    get_colours,
    try_get_first_key
)


class YouTubeChatDownloader(ChatDownloader):
    def __init__(self, updated_init_params={}):
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
    # __YT_REGEX = r'(?:/|%3D|v=|vi=)([0-9A-z-_]{11})(?:[%#?&]|$)'
    _YOUTUBE_API_BASE_TEMPLATE = '{}/{}/{}?continuation={}&pbj=1&hidden=false'
    _YOUTUBE_API_PARAMETERS_TEMPLATE = '&playerOffsetMs={}'

    # CLI argument allows users to specify a list of "types of messages" they want
    _TYPES_OF_MESSAGES = {
        'messages': [
            'liveChatTextMessageRenderer'  # normal message
        ],
        'superchat': [
            # superchat messages which appear in chat
            'liveChatMembershipItemRenderer',
            'liveChatPaidMessageRenderer',
            'liveChatPaidStickerRenderer',

            # superchat messages which appear ticker (at the top)
            'liveChatTickerPaidStickerItemRenderer',
            'liveChatTickerPaidMessageItemRenderer',
            'liveChatTickerSponsorItemRenderer',
        ],
        'banners': [
            'liveChatBannerRenderer',
            'liveChatBannerHeaderRenderer',
            # 'liveChatTextMessageRenderer'
        ],

        'donations':[
            'liveChatDonationAnnouncementRenderer'
        ],
        'engagement':[
            'liveChatViewerEngagementMessageRenderer', # message saying Live Chat replay is on
        ],
        'purchases':[
            'liveChatPurchasedProductMessageRenderer' # product purchased
        ],

        'mode_changes':[
            'liveChatModeChangeMessageRenderer' # e.g. slow mode enabled
        ],

        'other': [
            'liveChatPlaceholderItemRenderer' # placeholder
        ],
    }

    _KNOWN_MESSAGE_TYPES = []
    for message_type in _TYPES_OF_MESSAGES:
        _KNOWN_MESSAGE_TYPES += _TYPES_OF_MESSAGES[message_type]

    # _IMPORTANT_KEYS_AND_REMAPPINGS = {
    #     'timestampUsec': 'timestamp',
    #     'authorExternalChannelId': 'author_id',
    #     'authorName': 'author',
    #     'purchaseAmountText': 'amount',
    #     'message': 'message',
    #     'headerBackgroundColor': 'header_color',
    #     'bodyBackgroundColor': 'body_color',
    #     'timestampText': 'time_text',
    #     'amount': 'amount',
    #     'startBackgroundColor': 'body_color',
    #     'durationSec': 'ticker_duration',
    #     'detailText': 'message',
    #     'headerSubtext': 'message',  # equivalent to message - get runs
    #     'backgroundColor': 'body_color'
    # }

    _MESSAGE_FORMATTING_GROUPS_REGEX = r'\{(.*?)\{(.*?)?\}(.*?)\}'
    _MESSAGE_FORMATTING_INDEXES_REGEX = r'\|(?![^\[]*\])'
    _MESSAGE_FORMATTING_FORMATTING_REGEX = r'(.*)\[(.*)\]'

    @staticmethod
    def parse_youtube_link(text):
        if(text.startswith('/redirect')):  # is a redirect link
            info = dict(parse.parse_qsl(parse.urlsplit(text).query))
            return info['q'] if 'q' in info else ''
        elif(text.startswith('/watch')):  # is a youtube video link
            return YouTubeChatDownloader.YT_HOME + text
        elif(text.startswith('//')):
            return 'https:' + text
        else:  # is a normal link
            return text

    @staticmethod
    def parse_navigation_endpoint(navigation_endpoint, default_text=''):

        url = try_get(navigation_endpoint, lambda x: YouTubeChatDownloader.parse_youtube_link(
            x['commandMetadata']['webCommandMetadata']['url'])) or default_text

        return url

    @staticmethod
    def parse_runs(run_info):
        """ Reads and parses YouTube formatted messages (i.e. runs). """
        message_text = ''

        runs = run_info.get('runs')
        if(runs):
            for run in runs:
                if 'text' in run:
                    if 'navigationEndpoint' in run:  # is a link

                        # if something fails, use default text
                        message_text += YouTubeChatDownloader.parse_navigation_endpoint(
                            run['navigationEndpoint'], run['text'])

                    else:  # is a normal message
                        message_text += run['text']
                elif 'emoji' in run:
                    message_text += run['emoji']['shortcuts'][0]
                else:
                    raise ValueError('Unknown run: {}'.format(run))

        return message_text

    # liveChatAuthorBadgeRenderer
# YouTubeChatDownloader.

    @staticmethod
    def camel_case_split(word):
        return '_'.join(re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', word)).lower()

    @staticmethod
    def strip_live_chat_renderer(index):

        if index.startswith('liveChat'):  # remove prefix
            index = index[8:]
        if index.endswith('Renderer'):  # remove suffix
            index = index[0:-8:]

        return index

    @staticmethod
    def strip_color_text(text):
        if text.endswith('Color'):
            text = text[0:-5]
        return text

    @staticmethod
    def strip_action(text):
        # if text.startswith('add'):  # remove prefix
        #     text = text[3:]
        if text.endswith('Action'):  # remove suffix
            text = text[0:-6:]

        return text


# "addChatItemAction":{
#     "item":{
#         "liveChatViewerEngagementMessageRenderer":{

    # _IMPORTANT_KEYS_AND_REMAPPINGS = {
    #     'timestampUsec': 'timestamp',
    #     'authorExternalChannelId': 'author_id',
    #     'authorName': 'author',
    #     'purchaseAmountText': 'amount',
    #     'message': 'message',
    #     'headerBackgroundColor': 'header_color',
    #     'bodyBackgroundColor': 'body_color',
    #     'timestampText': 'time_text',
    #     'amount': 'amount',
    #     'startBackgroundColor': 'body_color',
    #     'durationSec': 'ticker_duration',
    #     'detailText': 'message',
    #     'headerSubtext': 'message',  # equivalent to message - get runs
    #     'backgroundColor': 'body_color'
    # }


# _GET_AUTHOR_PHOTOS
    # _SIMPLE_TEXT_REMAPPER =
    # _DO_NOTHING =
    # _CONVERT_TO_INT =
    #  =
    # _PARSE_MESSAGE_RUNS =

    # def _SIMPLE_TEXT_REMAPPER(x): return x.get('simpleText')
    # def _DO_NOTHING(x): return x
    # def _CONVERT_TO_INT(x): return int_or_none(x)
    # def _GET_AUTHOR_PHOTOS(x): return x.get('thumbnails')

    # def _PARSE_MESSAGE_RUNS(
    #     x): return YouTubeChatDownloader.parse_message_runs(x['runs'])

    # continuation_by_title_map = {
    #     x['title']: x['continuation']['reloadContinuationData']['continuation']
    #     for x in viewselector_submenuitems
    # }
    #_TEST = _parse_message_runs
    # .__func__


    @staticmethod
    def _parse_item(item):
        info = {}

        item_index = try_get_first_key(item)

        if(not item_index):
            print('ERROR 1')
            print(item)
            return info  # invalid # TODO log this


        item_info = item.get(item_index)

        # print(item_info.keys())
        # return info
        if(not item_info):
            print('ERROR 2')
            print(item)
            return info  # invalid # TODO log this

        for key in YouTubeChatDownloader._REMAPPING:
            index, mapping_function = YouTubeChatDownloader._REMAPPING[key]
            # print(mapping_function)
            # try:

            original_info = item_info.get(key)
            # if(key == 'actionButton'):
            #     print(item_info.keys())
            #     #print(key)
            #     print(original_info)
            if(original_info):
                info[index] = YouTubeChatDownloader._REMAP_FUNCTIONS[mapping_function](
                    original_info)

                # if(key == 'actionButton'):
                #     print('yuppppppp')
                #     print(original_info)
                #     print(index, info[index])
            else:  # this item does not contain a certain key. ignore it
                pass
            # except:
            #     print('ERROR 3')
            #     print(key, index, original_info)

                #print('key not in info')
                #print(key,': not in ->', item_info.keys())
                # item_info

            #index, mapping_function,item,
            # print(key, item_info)#.get(key)
#             #

    # _PARSE_COLOURS = lambda x : {
    #     strip_color_text(key) : x.get(key)
    #     for key in x

    # }
        # check for colour information
        for colour_key in YouTubeChatDownloader._COLOUR_KEYS:
            if(colour_key in item_info):  # if item has colour information
                if('colours' not in info):  # create colour dict if not set
                    info['colours'] = {}

                info['colours'][YouTubeChatDownloader.camel_case_split(
                    YouTubeChatDownloader.strip_color_text(colour_key))] = get_colours(item_info.get(colour_key)).get('hex')
            pass

        # check for sticker information

        # sticker = item_info.get('sticker')
        # if (sticker):
        #     info['sticker_info'] = {
        #         'images': sticker.get('thumbnails'),

        #     }

        # 'sticker', 'stickerDisplayWidth', 'stickerDisplayHeight'

        # TODO debugging for missing keys
        missing_keys = item_info.keys()-YouTubeChatDownloader._REMAPPING.keys() - \
            set(YouTubeChatDownloader._KEYS_TO_IGNORE +
                YouTubeChatDownloader._COLOUR_KEYS + YouTubeChatDownloader._STICKER_KEYS)
        if(missing_keys):
            # print(info['type'])
            print('missing_keys', missing_keys, 'for message_type',item_index)

            print(item_info)  # info
            print(info)
            print()

        # all messages should have the following

        #
        # info['id'] = item_info.get('id')

        item_endpoint = item_info.get('showItemEndpoint')
        if(item_endpoint):  # has additional information
            renderer = try_get(
                item_endpoint, (lambda x: x['showLiveChatItemEndpoint']['renderer']))
            # next(iter(item))
            if(renderer):
                info.update(YouTubeChatDownloader._parse_item(renderer))

            # update without overwriting ? TODO decide which to use
            #info.update({key: renderer[key] for key in renderer if key not in item})

        time_text = info.get('time_text')
        if(time_text):
            info['time_in_seconds'] = time_to_seconds(time_text)

        return info

    @staticmethod
    def parse_badges(badge_items):
        badges = []
        #author_badges = item.get('authorBadges')

        for badge in badge_items:
            parsed_badge = YouTubeChatDownloader._parse_item(badge)

            badges.append(parsed_badge.get('tooltip'))
        return badges

    @staticmethod
    def parse_thumbnails(item):

        # sometimes thumbnails come as a list
        if(isinstance(item, list)):
            item = item[0]  # rebase

        return item.get('thumbnails')

    @staticmethod
    def parse_action_button(item):
        # a =
        # print(a)
        return {
            'url': try_get(item, lambda x: YouTubeChatDownloader.parse_navigation_endpoint(x['buttonRenderer']['navigationEndpoint'])) or '',
            'text': try_get(item, lambda x: x['buttonRenderer']['text']['simpleText']) or ''
        }

    _REMAP_FUNCTIONS = {
        'do_nothing': lambda x: x,
        'simple_text': lambda x: x.get('simpleText'),
        'convert_to_int': lambda x: int_or_none(x),
        'get_thumbnails': lambda x: YouTubeChatDownloader.parse_thumbnails(x),
        'parse_runs': lambda x: YouTubeChatDownloader.parse_runs(x),
        'parse_badges': lambda x: YouTubeChatDownloader.parse_badges(x),

        'parse_icon': lambda x: x.get('iconType'),

        'parse_action_button': lambda x: YouTubeChatDownloader.parse_action_button(x),
    }

    _REMAPPING = {
        # 'youtubeID' : ('mapped_id', 'remapping_function')
        'id': ('id', 'do_nothing'),
        'authorExternalChannelId': ('author_id', 'do_nothing'),
        'authorName': ('author', 'simple_text'),
        'purchaseAmountText': ('amount', 'simple_text'),
        'message': ('message', 'parse_runs'),
        'timestampText': ('time_text', 'simple_text'),
        'timestampUsec': ('timestamp', 'convert_to_int'),
        'authorPhoto': ('author_images', 'get_thumbnails'),
        'tooltip': ('tooltip', 'do_nothing'),

        'icon': ('icon', 'parse_icon'),
        'authorBadges': ('author_badges', 'parse_badges'),

        # stickers
        'sticker': ('sticker_images', 'get_thumbnails'),

        # ticker_paid_message_item
        'fullDurationSec': ('ticker_duration', 'convert_to_int'),
        'amount': ('amount', 'simple_text'),


        # ticker_sponsor_item
        'detailText': ('message', 'parse_runs'),

        # author_badge
        'customThumbnail': ('badge_icons', 'get_thumbnails'),


        # membership_item
        'headerSubtext': ('message', 'parse_runs'),
        'sponsorPhoto': ('sponsor_icons', 'get_thumbnails'),

        # ticker_paid_sticker_item
        'tickerThumbnails': ('ticker_icons', 'get_thumbnails'),


        # deleted messages
        'deletedStateMessage': ('message', 'parse_runs'),
        'targetItemId': ('target_id', 'do_nothing'),

        'externalChannelId':  ('author_id', 'do_nothing'),

        # action buttons
        'actionButton': ('action', 'parse_action_button'),

        # addBannerToLiveChatCommand
        'text': ('message', 'parse_runs'),

        # donation_announcement
        'subtext': ('sub_message', 'parse_runs'),


    }

    _COLOUR_KEYS = [
        # paid_message
        'authorNameTextColor', 'timestampColor', 'bodyBackgroundColor',
        'headerTextColor', 'headerBackgroundColor', 'bodyTextColor',

        # paid_sticker
        'backgroundColor', 'moneyChipTextColor', 'moneyChipBackgroundColor',

        # ticker_paid_message_item
        'startBackgroundColor', 'amountTextColor', 'endBackgroundColor',

        # ticker_sponsor_item
        'detailTextColor'
    ]

    _STICKER_KEYS = [
        # to actually ignore
        'stickerDisplayWidth', 'stickerDisplayHeight',  # ignore

        # parsed elsewhere
        'sticker',
    ]

    _KEYS_TO_IGNORE = [
        # to actually ignore
        'contextMenuAccessibility', 'contextMenuEndpoint', 'trackingParams', 'accessibility',

        'contextMenuButton',

        # parsed elsewhere
        'showItemEndpoint',
        'durationSec'
    ]

    # _KNOWN_SHOW_TOOLTIP_TYPES = [
    #     'showLiveChatTooltipCommand'
    # ]

    _KNOWN_ADD_TICKER_TYPES = [
        'addLiveChatTickerItemAction'
    ]

    _KNOWN_ADD_ACTION_TYPES = [
        'addChatItemAction',
    ]

    # actions that have an 'item'
    _KNOWN_ITEM_ACTION_TYPES = _KNOWN_ADD_TICKER_TYPES + _KNOWN_ADD_ACTION_TYPES

    _KNOWN_REMOVE_ACTION_TYPES = [
        # [message deleted] or [message retracted]
        'markChatItemAsDeletedAction',
        'markChatItemsByAuthorAsDeletedAction'
    ]

    _KNOWN_ADD_BANNER_TYPES = [
        'addBannerToLiveChatCommand',
    ]

    _KNOWN_IGNORE_ACTION_TYPES = [
        'showLiveChatTooltipCommand'
    ]

    #_KNOWN_CHAT_ACTION_TYPES = _KNOWN_ADD_ACTION_TYPES + _KNOWN_REMOVE_ACTION_TYPES

    _KNOWN_ACTION_TYPES = _KNOWN_ADD_TICKER_TYPES + \
        _KNOWN_ITEM_ACTION_TYPES + _KNOWN_REMOVE_ACTION_TYPES + \
        _KNOWN_ADD_BANNER_TYPES + _KNOWN_IGNORE_ACTION_TYPES


    _KNOWN_SEEK_CONTINUATIONS = [
        'playerSeekContinuationData'
    ]

    _KNOWN_CHAT_CONTINUATIONS = [
        'invalidationContinuationData', 'timedContinuationData',
        'liveChatReplayContinuationData', 'reloadContinuationData'
    ]

    _KNOWN_CONTINUATIONS = _KNOWN_SEEK_CONTINUATIONS + _KNOWN_CHAT_CONTINUATIONS
    # _KNOWN_LIVE_CHAT_RENDERERS = [
    #     'liveChatViewerEngagementMessageRenderer',
    #     'liveChatPurchasedProductMessageRenderer',  # product purchased
    #     'liveChatPlaceholderItemRenderer',  # placeholder
    #     'liveChatModeChangeMessageRenderer'  # e.g. slow mode enabled
    #     'liveChatTextMessageRenderer'  # normal message
    #     'liveChatMembershipItemRenderer',
    #     'liveChatPaidMessageRenderer',
    #     'liveChatPaidStickerRenderer',
    #     'liveChatTickerPaidStickerItemRenderer',
    #     'liveChatTickerPaidMessageItemRenderer',
    #     'liveChatTickerSponsorItemRenderer',
    # ]

    def _get_initial_info(self, video_id):
        """ Get initial YouTube video information. """
        original_url = '{}/watch?v={}'.format(self._YT_HOME, video_id)
        html = self._session_get(original_url)

        info = re.search(self._YT_INITIAL_DATA_RE, html.text)

        if(not info):
            raise ParsingError(
                'Unable to parse video data. Please try again.')

        ytInitialData = json.loads(info.group(1))

        # print()
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
                error_message = self.parse_runs(
                    columns['conversationBar']['conversationBarRenderer']['availabilityMessage']['messageRenderer']['text'])
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

    def _get_replay_info(self, continuation, offset_microseconds=None):
        """Get YouTube replay info, given a continuation or a certain offset."""
        url = self._YOUTUBE_API_BASE_TEMPLATE.format(self._YT_HOME,
                                                     'live_chat_replay', 'get_live_chat_replay', continuation)
        if(offset_microseconds is not None):
            url += self._YOUTUBE_API_PARAMETERS_TEMPLATE.format(
                offset_microseconds)
        return self._get_continuation_info(url)

    def _get_live_info(self, continuation):
        """Get YouTube live info, given a continuation."""
        url = self._YOUTUBE_API_BASE_TEMPLATE.format(self._YT_HOME,
                                                     'live_chat', 'get_live_chat', continuation)
        return(self._get_continuation_info(url))

    def _get_continuation_info(self, url):
        """Get continuation info for a YouTube video."""
        json = self._session_get_json(url)
        if('continuationContents' in json['response']):
            return json['response']['continuationContents']['liveChatContinuation']
        else:
            raise NoContinuation

    # TODO move to utils
    def _ensure_seconds(self, time, default=None):
        """Ensure time is returned in seconds."""
        if(not time):  # if empty, return default
            return default

        try:
            return int(time)
        except ValueError:
            return time_to_seconds(time)
        except:
            return default

    def _format_item(self, result, item):

        # split by | not enclosed in []
        split = re.split(
            self._MESSAGE_FORMATTING_INDEXES_REGEX, result.group(2))
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
                        value = microseconds_to_timestamp(
                            item[index], format=formatting)
                    # possibility for more formatting options

                    # return value if index matches, otherwise keep searching
                return '{}{}{}'.format(result.group(1), value, result.group(3))

        return ''  # no match, return empty

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

        # 'message_type':'messages'

       # =0, , , chat_type='live',
    # _DEFAULT_PARAMS

    # def parse_action(self, params, action):

    def get_chat_by_video_id(self, video_id, params):
        """ Get chat messages for a YouTube video. """

        initial_info = self._get_initial_info(video_id)

        # print(initial_info)

        start_time = self._ensure_seconds(params.get('start_time'), None)
        end_time = self._ensure_seconds(params.get('end_time'), None)

        #messages = []

        # Top chat replay - Some messages, such as potential spam, may not be visible
        # Live chat replay - All messages are visible

        chat_type = params.get('chat_type', 'live')

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
        offset_milliseconds = start_time * \
            1000 if isinstance(start_time, int) else None

        first_time = True
        while True:
            info = None
            # try:
            # the following can raise NoContinuation error or JSONParseError

            while(info is None):
                try:
                    if(is_live):
                        info = self._get_live_info(continuation)
                    else:
                        # must run to get first few messages, otherwise might miss some
                        if(first_time):
                            info = self._get_replay_info(continuation)  # , 0
                        else:
                            info = self._get_replay_info(
                                continuation, offset_milliseconds)
                except JSONParseError as e:
                    print('error',e)
                    print('retrying')

            # except NoContinuation:
                # print('No continuation found, stream may have ended.')
                # break
            actions = info.get('actions')
            if(actions):
                for action in actions:
                    data = {}

                    # if it is a replay chat item action, must re-base it
                    replay_chat_item_action = action.get(
                        'replayChatItemAction')
                    if(replay_chat_item_action):
                        offset_time = replay_chat_item_action.get(
                            'videoOffsetTimeMsec')
                        if(offset_time):
                            data['video_offset_time_msec'] = int(offset_time)
                            # TODO make sure same as twitch
                        action = replay_chat_item_action['actions'][0]

                    original_action_type = try_get_first_key(action)

                    # print('original_action_type',original_action_type)



                    if(original_action_type not in self._KNOWN_ACTION_TYPES):
                        # TODO show warning in verbose
                        # different kind of action
                        print('Unknown action')
                        print(original_action_type)
                        pass
                        data['action_type'] = 'unknown' # TODO temp
                    else:
                        data['action_type'] = YouTubeChatDownloader.camel_case_split(
                        YouTubeChatDownloader.strip_action(original_action_type))

                    #item = None
                    original_message_type = None

                    #print(original_action_type,action)
                    if(original_action_type in self._KNOWN_ITEM_ACTION_TYPES + self._KNOWN_REMOVE_ACTION_TYPES):
                        if(original_action_type in self._KNOWN_ITEM_ACTION_TYPES):
                            item = try_get(
                                action, lambda x: x[original_action_type]['item'])
                        else:  # (original_action_type in self._KNOWN_REMOVE_ACTION_TYPES)
                            # try_get(action, lambda x: x[original_action_type])
                            item = action

                        original_message_type = try_get_first_key(item)
                        parsed_item = self._parse_item(item)
                        # print(parsed_item)

                        if not parsed_item:
                            print('EMPTY PARSE')
                            print(item)

                        parsed_item.update(data)  # add initial info, if any
                        data = parsed_item

                    # other actions which do not have similar working
                    elif(original_action_type in self._KNOWN_ADD_BANNER_TYPES):
                        item = try_get(
                            action, lambda x: x[original_action_type]['bannerRenderer'])

                        original_message_type = try_get_first_key(item) #next(iter(item))
                        #item = item
                        if(item):
                            header = item[original_message_type].get('header')
                            parsed_header = self._parse_item(header)
                            header_message = parsed_header.get('message')

                            contents = item[original_message_type].get(
                                'contents')
                            parsed_contents = self._parse_item(contents)

                            data.update(parsed_header)
                            data.update(parsed_contents)
                            data['header_message'] = header_message
                            # print(data)

                    elif(original_action_type in self._KNOWN_IGNORE_ACTION_TYPES):

                        continue
                        # ignore these
                    else:
                        print('UNKNOWN ACTION TYPE')
                        print(original_action_type)
                        print(action)
                        item = None

                    # can ignore message
                    if(not original_message_type):  # no type
                        # TODO error? unknown message type
                        print('no type')
                        print(original_action_type)
                        print(item)
                        continue
                    else:
                        data['message_type'] = YouTubeChatDownloader.camel_case_split(
                            YouTubeChatDownloader.strip_live_chat_renderer(original_message_type))

                        if(original_message_type not in self._KNOWN_MESSAGE_TYPES):
                            print('UNKNOWN MESSAGE TYPE', original_message_type)
                            print(item)
                            # TODO debug


                    # elif(original_message_type in self._TYPES_OF_MESSAGES['other']):
                    #     print('other, skip')
                    #     continue

                    # TODO make this param a list for more variety
                    types_of_messages_to_add = params.get('message_type')

                    # user wants everything, keep going TODO True temp
                    if(True or types_of_messages_to_add == 'all'):
                        pass


                    #
                    else:
                        # check whether to skip this message or not, based on its type
                        for key in self._TYPES_OF_MESSAGES :
                            # user does not want a message type + message is that type
                            if(types_of_messages_to_add != key and original_message_type in self._TYPES_OF_MESSAGES[key]):
                                continue



                    # if from a replay, check whether to skip this message or not, based on its time
                    if(not is_live):
                        time_in_seconds = data.get('time_in_seconds', 0)
                        # assume message is at beginning if it does not have a time component

                        not_after_start = start_time is not None and time_in_seconds < start_time
                        not_before_end = end_time is not None and time_in_seconds > end_time

                        #print(first_time, not_after_start, not_before_end)
                        if(first_time and not_after_start):
                            continue  # first time and invalid start time
                        elif(not_after_start or not_before_end):
                            return  # while actually searching, if time is invalid

                    # valid timing, add
                    params.get('messages').append(data)

                    callback = params.get('callback')
                    if(not callback):
                        # print if it is not a ticker message (prevents duplicates)
                        # print(json.dumps(data))
                        #print('=', end='', flush=True)
                        # if(original_action_type not in self._KNOWN_ADD_TICKER_TYPES):
                        #     pass

                        if(original_action_type in self._KNOWN_ADD_ACTION_TYPES):
                            pass # is a chat message, print it
                            # TODO decide whether to add delted or not

                            # self.print_item(data)

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

            # if(len(info['continuations'])>1):
            #     print('more than 1 continuation, missing info?')
            #     print(info)

            cont = info.get('continuations')
            no_continuation = True # assume there are no more chat continuations
            #print('There are',len(cont),'continuations')
            for c in cont or []:
                #print(c)
                continuation_key = try_get_first_key(c)
                continuation_info = c[continuation_key]

                continuation_value = continuation_info.get('continuation')

                if(continuation_key in self._KNOWN_CHAT_CONTINUATIONS):

                    # set new chat continuation
                    continuation = continuation_value # overwrite if there is continuation data

                    # there is a chat continuation
                    no_continuation = False

                elif(continuation_key in self._KNOWN_SEEK_CONTINUATIONS):
                    pass
                    # ignore these continuations
                else:
                    # TODO debug
                    print('UNKNOWN CONTINUATION', continuation_key)
                    print(c)

                # sometimes continuation contains timeout info
                timeout = continuation_info.get('timeoutMs')
                if timeout:
                    # must wait before calling again
                    # prevents 429 errors (too many requests)
                    time.sleep(timeout/1000)



            if(no_continuation): # no continuation, end
                break

            if(first_time):
                first_time = False
            print('Total:',len(params.get('messages')))

    # override base method

    def get_chat_messages(self, params):
        super().get_chat_messages(params)

        url = params.get('url')
        messages = params.get('messages')

        match = re.search(self._VALID_URL, url)

        if(match):

            if(match.group('id')):  # normal youtube video
                return self.get_chat_by_video_id(match.group('id'), params)

            else:  # TODO add profile, etc.
                pass
