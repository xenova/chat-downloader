
from .common import (
    BaseChatDownloader,
    Chat,
    Remapper as r,
    Image
)

from ..errors import (
    ChatDownloaderError,
    NoChatReplay,
    ChatDisabled,
    NoContinuation,
    ParsingError,
    VideoUnavailable,
    LoginRequired,
    VideoUnplayable,
    InvalidParameter,
    UserNotFound,
    VideoNotFound,
    NoVideos
)
from ..utils.timed_utils import interruptible_sleep

from ..utils.core import (
    multi_get,
    time_to_seconds,
    seconds_to_time,
    int_or_none,
    float_or_none,
    arbg_int_to_rgba,
    rgba_to_hex,
    try_get_first_key,
    try_get_first_value,
    remove_prefixes,
    remove_suffixes,
    camel_case_split,
    ensure_seconds,
    attempts,
    try_parse_json,
    regex_search,
    parse_iso8601,
    get_title_of_webpage
)

from ..debugging import (log, debug_log)

from itertools import islice
import time
import random
import re
import hashlib
from requests.exceptions import RequestException
from json.decoder import JSONDecodeError
from urllib import parse


class YouTubeChatDownloader(BaseChatDownloader):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._initialize_consent()

    _NAME = 'youtube.com'

    _SITE_DEFAULT_PARAMS = {
        'format': 'youtube',
    }

    _TESTS = [
        # Get top live streams
        # https://www.youtube.com/results?search_query&sp=CAMSAkAB


        # OTHER:
        # Japanese characters and lots of superchats
        # https://www.youtube.com/watch?v=UlemRwXYWHg

        # strange end times:
        # https://www.youtube.com/watch?v=DzEbfQI4TPQ
        # https://www.youtube.com/watch?v=7PPnCOhkxqo

        # purchased a product linked to the YouTube channel merchandising
        # https://youtu.be/y5ih7nqEoc4


        # TESTING FOR CORRECT FUNCIONALITY
        {
            'name': 'Get chat messages from livestream',
            'params': {
                'url': 'https://www.youtube.com/watch?v=jfKfPfyJRdk',
                'timeout': 5
            }
        },
        {
            'name': 'Get chat messages from livestream, using channel id.',
            'params': {
                'url': 'https://www.youtube.com/channel/UCSJ4gkVC6NrvII8umztf0Ow',
                'timeout': 5
            }
        },
        {
            'name': 'Get chat messages from livestream, using custom url (1).',
            'params': {
                'url': 'https://www.youtube.com/c/lofigirl',
                'timeout': 5
            }
        },
        {
            'name': 'Get chat messages from livestream, using custom url (2).',
            'params': {
                'url': 'https://www.youtube.com/lofigirl',
                'timeout': 5
            }
        },
        {
            'name': 'Get chat messages from livestream, using user id.',
            'params': {
                'url': 'https://www.youtube.com/user/YellowBrickCinema',
                'timeout': 5
            }
        },
        {
            'name': 'Get chat messages from live chat replay',
            'params': {
                'url': 'https://www.youtube.com/watch?v=wXspodtIxYU',
                'max_messages': 10
            },

            'expected_result': {
                'message_types': ['text_message'],
                'action_types': ['add_chat_item'],
                'messages_condition': lambda messages: 0 < len(messages) <= 10,
            }
        },
        {
            'name': 'Get top chat messages from live chat replay',
            'params': {
                'url': 'https://www.youtube.com/watch?v=wXspodtIxYU',
                'start_time': 0,
                'end_time': 20,
                'chat_type': 'top'
            },
            'expected_result': {
                'message_types': ['text_message'],
                'action_types': ['add_chat_item'],
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },
        {
            'name': 'Get superchat and ticker messages from live chat replay',
            'params': {
                'url': 'https://www.youtube.com/watch?v=UlemRwXYWHg',
                'end_time': 20,
                'message_groups': ['superchat', 'tickers']
            },
            'expected_result': {
                'message_types': ['paid_message', 'ticker_paid_message_item', 'membership_item', 'ticker_sponsor_item', 'paid_sticker', 'ticker_paid_sticker_item'],
                'action_types': ['add_chat_item', 'add_live_chat_ticker_item'],
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },
        {
            'name': 'Get all messages from live chat replay',
            'params': {
                'url': 'https://www.youtube.com/watch?v=97w16cYskVI',
                'end_time': 50,
                'message_types': ['all']
            },
            'expected_result': {
                'message_types': ['viewer_engagement_message', 'paid_message', 'ticker_paid_message_item', 'text_message', 'paid_sticker', 'ticker_paid_sticker_item'],
                'action_types': ['add_chat_item', 'add_live_chat_ticker_item'],
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },
        {
            'name': 'Get messages from a premiere',  # Premiere
            'params': {
                'url': 'https://www.youtube.com/watch?v=zVCs9Cug_qM',
                'start_time': 0,
                'end_time': 20,
            },
            'expected_result': {
                'message_types': ['text_message'],
                'action_types': ['add_chat_item'],
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },
        {
            'name': 'Chat replay with donations',
            'params': {
                'url': 'https://www.youtube.com/watch?v=Ih2WTyY62J4',
                'start_time': 0,
                'end_time': 40,
                'message_groups': ['donations']
            },
            'expected_result': {
                'message_types': ['donation_announcement'],
                'action_types': ['add_chat_item'],
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },
        {  # https://github.com/xenova/chat-downloader/issues/178#issuecomment-1330029347
            'name': 'Chat replay with membership gifts',
            'params': {
                'url': 'https://www.youtube.com/watch?v=cb0h-KbpDo8',
                'start_time': '5:22:20',
                'end_time': '5:22:35',
                'message_groups': ['all']
            },
            'expected_result': {
                'message_types': ['text_message', 'sponsorships_gift_purchase_announcement', 'ticker_sponsor_item'],
                'action_types': ['add_chat_item', 'add_live_chat_ticker_item'],
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },

        {
            'name': 'Get chat messages from an unplayable stream.',
            'params': {
                'url': 'https://www.youtube.com/watch?v=V2Afni3S-ok',
                'start_time': 10,
                'end_time': 100,
            },
            'expected_result': {
                'message_types': ['text_message'],
                'action_types': ['add_chat_item'],
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },
        {  # https://github.com/xenova/chat-downloader/issues/175#issue-1438381085
            'name': 'Chat replay with a message that has no author name',
            'params': {
                'url': 'https://www.youtube.com/watch?v=-JU0rbfPECY',
                'timeout': 5,
                'start_time': '1:53:29',
                'end_time': '1:53:30',
            }
        },



        # TESTING FOR ERRORS
        {
            'name': 'Video does not exist',
            'params': {
                'url': 'https://www.youtube.com/watch?v=xxxxxxxxxxx',
            },
            'expected_result': {
                'error': VideoUnavailable,
            }
        },
        {
            'name': 'This video is no longer available due to a copyright claim by International Olympic Committee.',
            'params': {
                'url': 'https://www.youtube.com/watch?v=cjk2UKkzY0g',
            },
            'expected_result': {
                'error': VideoUnavailable,
            }
        },
        {
            'name': 'This video is not available.',  # YouTube Premium
            'params': {
                'url': 'https://www.youtube.com/watch?v=i1Ko8UG-Tdo',
            },
            'expected_result': {
                'error': VideoUnplayable,
            }
        },
        {
            'name': 'This video is not available.',  # Rental video preview
            'params': {
                'url': 'https://www.youtube.com/watch?v=yYr8q0y5Jfg',
            },
            'expected_result': {
                'error': VideoUnplayable,
            }
        },
        {
            # The following content has been identified by the YouTube community
            # as inappropriate or offensive to some audiences.
            'name': "This video has been removed for violating YouTube's policy on hate speech. Learn more about combating hate speech in your country.",  # Rental video preview
            'params': {
                'url': 'https://www.youtube.com/watch?v=6SJNVb0GnPI',
            },
            'expected_result': {
                'error': VideoUnavailable,
            }
        },
        {
            'name': 'Members-only content',
            'params': {
                'url': 'https://www.youtube.com/watch?v=vprErlL1w2E',
            },
            'expected_result': {
                'error': VideoUnplayable,
            }
        },
        {
            'name': 'Chat is disabled for this live stream',
            'params': {
                'url': 'https://www.youtube.com/watch?v=XWq5kBlakcQ',
            },
            'expected_result': {
                'error': ChatDisabled,
            }
        },
        {
            'name': 'Live chat replay has been turned off for this video',
            'params': {
                'url': 'https://www.youtube.com/watch?v=7lGZvbasx6A',
            },
            'expected_result': {
                'error': NoChatReplay,
            }
        },

        {
            'name': 'Video is private',
            'params': {
                'url': 'https://www.youtube.com/watch?v=ijFMXqa-N0c',
            },
            'expected_result': {
                'error': LoginRequired,
            }
        },
        {
            'name': 'The uploader has not made this video available in your country.',
            'params': {
                'url': 'https://www.youtube.com/watch?v=sJL6WA-aGkQ',
            },
            'expected_result': {
                'error': VideoUnplayable,
            }
        },
        {
            'name': 'This live stream recording is not available.',
            'params': {
                'url': 'https://www.youtube.com/watch?v=qEJwOuvDf7I',
            },
            'expected_result': {
                'error': VideoUnplayable,
            }
        },
        {
            # Age restricted
            'name': 'Sign in to confirm your age. This video may be inappropriate for some users.',
            'params': {
                'url': 'https://www.youtube.com/watch?v=WaOKSUlf4TM',
            },
            'expected_result': {
                'error': LoginRequired,
            }
        },

        # Potential parsing errors
        {
            'name': "Parsing error with '};' inside yt initial data (1)",
            'params': {
                'url': 'https://www.youtube.com/watch?v=CHqg6qOn4no',
            },
            'expected_result': {
                'error': NoChatReplay,
            }
        },
        {
            'name': "Parsing error with '};' inside yt initial data (2)",
            'params': {
                'url': 'https://www.youtube.com/watch?v=gVfgbahppCY',
            },
            'expected_result': {
                'error': NoChatReplay,
            }
        },
        {
            'name': 'Title with JS-like syntax "};"',
            'params': {
                'url': 'https://www.youtube.com/watch?v=lsguqyKfVQg',
            },
            'expected_result': {
                'error': NoChatReplay,
            }
        },

        # Clips
        {
            'name': 'Chat replay of clip (past broadcast)',
            'params': {
                'url': 'https://www.youtube.com/clip/Ugy_1IfsnZUWZSXL6C94AaABCQ',
            },
            'expected_result': {
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },
        {
            'name': 'Chat replay of clip (premiere)',
            'params': {
                'url': 'https://www.youtube.com/clip/UgzNZCNnPzq-M3_Utjl4AaABCQ',
            },
            'expected_result': {
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },
        {
            'name': 'Clip does not have a chat replay.',
            'params': {
                'url': 'https://www.youtube.com/clip/UgwVu73xQ5FUiGnteZJ4AaABCQ',
            },
            'expected_result': {
                'error': NoChatReplay,
            }
        },
        {
            'name': 'Sign in to confirm your age. This clip may be inappropriate for some users.',
            'params': {
                'url': 'https://www.youtube.com/clip/UgyfnqwleyOmnO-qA1h4AaABCQ',
            },
            'expected_result': {
                'error': LoginRequired,
            }
        },
        {
            'name': "Clip not available. The clip can be unavailable if it was deleted, or if the video it's based on was removed or edited.",
            'params': {
                'url': 'https://youtube.com/clip/UgxJiPo-4EeSYDfrYp94AaABCQ',
            },
            'expected_result': {
                'error': VideoUnavailable,
            }
        },
        {
            'name': 'Clip does not exist',
            'params': {
                'url': 'https://youtube.com/clip/x',
            },
            'expected_result': {
                'error': VideoNotFound,
            }
        }
    ]

    _YT_INITIAL_BOUNDARY_RE = r'\s*(?:var\s+(?:meta|head)|</script|\n)'
    _YT_INITIAL_DATA_RE = r'(?:window\s*\[\s*["\']ytInitialData["\']\s*\]|ytInitialData)\s*=\s*({.+?})\s*;' + \
        _YT_INITIAL_BOUNDARY_RE
    _YT_INITIAL_PLAYER_RESPONSE_RE = r'ytInitialPlayerResponse\s*=\s*({.+?})\s*;' + \
        _YT_INITIAL_BOUNDARY_RE
    _YT_CFG_RE = r'ytcfg\.set\s*\(\s*({.+?})\s*\)\s*;'

    _YT_HOME = 'https://www.youtube.com'
    _YT_VIDEO_TEMPLATE = _YT_HOME + '/watch?v={}'
    _YT_CLIP_TEMPLATE = _YT_HOME + '/clip/{}'

    _YOUTUBE_INIT_API_TEMPLATE = _YT_HOME + '/{}?continuation={}'
    _YOUTUBE_CHAT_API_TEMPLATE = _YT_HOME + '/youtubei/v1/live_chat/get_{}?key={}'
    _YOUTUBE_BROWSE_API_TEMPLATE = _YT_HOME + '/youtubei/v1/browse?key={}'

    _MESSAGE_GROUPS = {
        'messages': [
            'text_message'  # normal message
        ],
        'superchat': [
            # superchat messages which appear in chat
            'membership_item',
            'paid_message',
            'paid_sticker',

            # Gifts
            'sponsorships_gift_purchase_announcement',
        ],
        'tickers': [
            # superchat messages which appear ticker (at the top)
            'ticker_paid_sticker_item',
            'ticker_paid_message_item',
            'ticker_sponsor_item',
        ],
        'banners': [
            'banner',
            'banner_header'
        ],

        'donations': [
            'donation_announcement'
        ],
        'engagement': [
            # message saying live chat replay is on
            'viewer_engagement_message',
        ],
        'purchases': [
            'purchased_product_message'  # product purchased
        ],

        'mode_changes': [
            'mode_change_message'  # e.g. slow mode enabled
        ],

        'deleted': [
            'deleted_message'
        ],
        'bans': [
            'ban_user'
        ],

        'placeholder': [
            'placeholder_item'  # placeholder
        ]
    }

    _MESSAGE_TYPES = ['all']
    for _group in _MESSAGE_GROUPS:
        _MESSAGE_TYPES += _MESSAGE_GROUPS[_group]

    # Regex provided by youtube-dl

    # TODO differentiate /user/x, /c/y and /channel/UC...

    _VALID_URLS = {
        '_get_chat_by_video_id': r'''(?x)^
                     (
                         # http(s):// or protocol-independent URL
                         (?:https?://|//)
                         (?:(?:(?:(?:\w+\.)?[yY][oO][uU][tT][uU][bB][eE](?:-nocookie|kids)?\.com/|
                            youtube\.googleapis\.com/)                        # the various hostnames, with wildcard subdomains
                         (?:.*?\#/)?                                          # handle anchor (#/) redirect urls
                         (?:                                                  # the various things that can precede the ID:
                             # v/ or embed/ or e/
                             (?:(?:v|embed|e)/(?!videoseries))
                             |(?:                                             # or the v= param in all its forms
                                 # preceding watch(_popup|.php) or nothing (like /?v=xxxx)
                                 (?:(?:watch|movie)(?:_popup)?(?:\.php)?/?)?
                                 (?:\?|\#!?)                                  # the params delimiter ? or # or #!
                                 # any other preceding param (like /?s=tuff&v=xxxx or ?s=tuff&amp;v=V36LpHqtcDY)
                                 (?:.*?[&;])??
                                 v=
                             )
                         ))
                         |(?:
                            youtu\.be                                        # just youtu.be/xxxx
                         )/)
                     )?                                                       # all until now is optional -> you can pass the naked ID
                     # here is it! the YouTube video ID
                     (?P<id>[0-9A-Za-z_-]{11})''',

        '_get_chat_by_clip_id': r'''(?x)
                (?:https?://|//)
                    (?:\w+\.)?
                    (?:
                        youtube?\.com
                    )/clip/
                    (?P<id>[a-zA-Z0-9_-]+)''',

        # while this does match 'watch' urls, it will never
        # return this since the above regex is run before this
        '_get_chat_by_user': r'''(?x)
                (?:https?://|//)
                    (?:\w+\.)?
                    (?:
                        youtube(?:kids)?\.com
                    )/
                    (?:
                        (?P<type>channel/|c/|user/|@)
                    )?
                    (?P<id>[a-zA-Z0-9_-]+)'''
    }

    @staticmethod
    def _get_source_image_url(url):
        index = url.find('=')
        if index >= 0:
            return url[0:url.index('=')]
        else:
            return url

    @staticmethod
    def _parse_youtube_link(text):
        if text.startswith(('/redirect', 'https://www.youtube.com/redirect')):  # is a redirect link
            info = dict(parse.parse_qsl(parse.urlsplit(text).query))
            return info.get('q') or ''
        elif text.startswith('//'):
            return 'https:' + text
        elif text.startswith('/'):  # is a youtube link e.g. '/watch','/results'
            return YouTubeChatDownloader._YT_HOME + text
        else:  # is a normal link
            return text

    @staticmethod
    def _parse_navigation_endpoint(navigation_endpoint, default_text=''):
        try:
            return YouTubeChatDownloader._parse_youtube_link(
                navigation_endpoint['commandMetadata']['webCommandMetadata']['url'])
        except Exception:
            return default_text

    @staticmethod
    def _parse_text(info):
        return YouTubeChatDownloader._parse_runs(info)['message'] or YouTubeChatDownloader._get_simple_text(info)

    @staticmethod
    def _parse_runs(run_info, parse_links=True):
        """ Reads and parses YouTube formatted messages (i.e. runs). """

        # TODO separate _parse_runs logic?

        message_info = {
            'message': ''
        }

        if not isinstance(run_info, dict):
            return message_info

        message_emotes = {}

        runs = run_info.get('runs') or []
        for run in runs:
            if 'text' in run:
                if parse_links and 'navigationEndpoint' in run:  # is a link and must parse

                    # if something fails, use default text
                    message_info['message'] += YouTubeChatDownloader._parse_navigation_endpoint(
                        run['navigationEndpoint'], run['text'])

                else:  # is a normal message
                    message_info['message'] += run['text']

            elif 'emoji' in run:
                emoji = run['emoji']
                emoji_id = emoji.get('emojiId')

                name = multi_get(emoji, 'shortcuts', 0) or emoji_id

                if emoji_id and emoji_id not in message_emotes:

                    # TODO change to remapping?
                    message_emotes[emoji_id] = {
                        'id': emoji_id,
                        'name': name,
                        'shortcuts': emoji.get('shortcuts'),
                        'search_terms': emoji.get('searchTerms'),
                        'images': YouTubeChatDownloader._parse_thumbnails(emoji.get('image', {})),
                        'is_custom_emoji': emoji.get('isCustomEmoji', False)
                    }

                message_info['message'] += name

            else:
                # unknown run
                message_info['message'] += str(run)

        if message_emotes:
            message_info['emotes'] = list(message_emotes.values())

        return message_info

    @staticmethod
    def _parse_item(item, info=None, offset=0):
        if info is None:
            info = {}
        # info is starting point
        item_index = try_get_first_key(item)
        item_info = item.get(item_index)

        if not item_info:
            return info

        for key in item_info:
            r.remap(info, YouTubeChatDownloader._REMAPPING,
                    key, item_info[key])

        # check for colour information
        for colour_key in YouTubeChatDownloader._COLOUR_KEYS:
            if colour_key in item_info:  # if item has colour information
                rgba_colour = arbg_int_to_rgba(item_info[colour_key])
                hex_colour = rgba_to_hex(rgba_colour)
                new_key = camel_case_split(
                    colour_key.replace('Color', 'Colour'))
                info[new_key] = hex_colour

        item_endpoint = item_info.get('showItemEndpoint')
        if item_endpoint:  # has additional information
            renderer = multi_get(
                item_endpoint, 'showLiveChatItemEndpoint', 'renderer')

            if renderer:
                info.update(YouTubeChatDownloader._parse_item(
                    renderer, offset=offset))

        header = item_info.get('header')
        if header:
            info.update(YouTubeChatDownloader._parse_item(
                header, offset=offset))

        BaseChatDownloader._move_to_dict(info, 'author')

        # Sometimes YouTube channels can have no names, so, account for this
        if 'author' in info and 'name' not in info['author']:
            info['author']['name'] = ''

        # TODO determine if youtube glitch has occurred
        # round(time_in_seconds/timestamp) == 1
        time_in_seconds = info.get('time_in_seconds')
        time_text = info.get('time_text')

        if time_in_seconds is not None:

            if time_text is not None:
                # All information was provided, check if time_in_seconds is <= 0
                # For some reason, YouTube sets the video offset to 0 if the message
                # was sent before the stream started. This fixes that:
                if time_in_seconds <= 0:
                    info['time_in_seconds'] = time_to_seconds(time_text)
            else:
                # recreate time text from time in seconds
                info['time_text'] = seconds_to_time(time_in_seconds)

        elif time_text is not None:  # doesn't have time in seconds, but has time text
            info['time_in_seconds'] = time_to_seconds(time_text)
        else:
            pass
            # has no current video time information
            # (usually live video or a sub-item)

        # non-zero, non-null offset and has time_in_seconds info
        if offset and 'time_in_seconds' in info:
            info['time_in_seconds'] -= offset
            info['time_text'] = seconds_to_time(info['time_in_seconds'])

        if 'message' not in info:  # Ensure the parsed item contains the 'message' key
            info['message'] = None

        return info

    @staticmethod
    def _parse_badges(badge_items):
        badges = []

        for badge in badge_items:
            to_add = {}
            parsed_badge = YouTubeChatDownloader._parse_item(badge)

            title = parsed_badge.pop('tooltip', None)
            if title:
                to_add['title'] = title

            icon = parsed_badge.pop('icon', None)
            if icon:
                to_add['icon_name'] = icon.lower()

            badge_icons = parsed_badge.pop('badge_icons', None)
            if badge_icons:
                to_add['icons'] = []

                url = None
                for icon in badge_icons:
                    url = icon.get('url')
                    if url:
                        matches = re.search(r'=s(\d+)', url)
                        if matches:
                            size = int(matches.group(1))
                            to_add['icons'].append(
                                Image(url, size, size).json())
                if url:
                    to_add['icons'].insert(0, Image(
                        YouTubeChatDownloader._get_source_image_url(url), image_id='source').json())

            badges.append(to_add)

            # if 'member'
            # remove the tooltip afterwards
            # print(badges)
        return badges

    @staticmethod
    def _parse_thumbnails(item):

        # sometimes thumbnails come as a list
        if isinstance(item, list):
            item = item[0]  # rebase

        # TODO add source:
        # https://yt3.ggpht.com/ytc/AAUvwnhBYeK7_iQTJbXe6kIMpMlCI2VsVHhb6GBJuYeZ=s32-c-k-c0xffffffff-no-rj-mo
        # https://yt3.ggpht.com/ytc/AAUvwnhBYeK7_iQTJbXe6kIMpMlCI2VsVHhb6GBJuYeZ

        thumbnails = item.get('thumbnails') or []
        final = list(map(lambda x: Image(**x).json(), thumbnails))

        if len(final) > 0:
            final.insert(0, Image(
                YouTubeChatDownloader._get_source_image_url(final[0]['url']), image_id='source').json())

        return final

    @staticmethod
    def _parse_action_button(item):
        endpoint = multi_get(item, 'buttonRenderer', 'navigationEndpoint')

        return {
            'url': YouTubeChatDownloader._parse_navigation_endpoint(endpoint) if endpoint else '',
            'text': multi_get(item, 'buttonRenderer', 'text', 'simpleText') or ''
        }

    @staticmethod
    def _get_simple_text(item):
        return item.get('simpleText')

    _CURRENCY_SYMBOLS = {
        '$': 'USD',
        'A$': 'AUD',
        'CA$': 'CAD',
        'HK$': 'HKD',
        'MX$': 'MXN',
        'NT$': 'TWD',
        'NZ$': 'NZD',
        'R$': 'BRL',
        '£': 'GBP',
        '€': 'EUR',
        '₹': 'INR',
        '₪': 'ILS',
        '₱': 'PHP',

        '₩': 'KRW',
        '￦': 'KRW',

        '¥': 'JPY',
        '￥': 'JPY',
    }

    # All other currency symbols use the ISO 4217 format:
    # https://en.wikipedia.org/wiki/ISO_4217
    # e.g. 'CHF', 'COP', 'HUF', 'PLN', 'RUB', 'SEK', 'PEN', 'ARS', 'CLP', 'NOK', 'BAM', 'SGD'

    @staticmethod
    def _parse_currency(item):
        mixed_text = item.get('simpleText') or str(item)

        info = re.split(r'([\d,\.]+)', mixed_text)
        if len(info) >= 2:  # Correct parse
            currency_symbol = info[0].strip()
            currency_code = YouTubeChatDownloader._CURRENCY_SYMBOLS.get(
                currency_symbol, currency_symbol)
            amount = float(info[1].replace(',', ''))

        else:  # Unable to get info
            amount = float(re.sub(r'[^\d\.]+', '', mixed_text))
            currency_symbol = currency_code = None

        return {
            'text': mixed_text,
            'amount': amount,
            'currency': currency_code,  # ISO_4217
            'currency_symbol': currency_symbol
        }

    _REMAPPING = {
        'id': 'message_id',
        'authorExternalChannelId': 'author_id',
        'authorName': r('author_name', _get_simple_text),
        # TODO author_display_name
        'purchaseAmountText': r('money', _parse_currency),
        'message': r(None, _parse_runs, True),
        'timestampText': r('time_text', _get_simple_text),
        'timestampUsec': r('timestamp', int_or_none),

        'authorPhoto': r('author_images', _parse_thumbnails),

        'tooltip': 'tooltip',

        'icon': r('icon', lambda x: x.get('iconType')),
        'authorBadges': r('author_badges', _parse_badges),

        # stickers
        'sticker': r('sticker_images', _parse_thumbnails),

        # ticker_paid_message_item
        'fullDurationSec': r('ticker_duration', int_or_none),
        'amount': r('money', _parse_currency),


        # ticker_sponsor_item
        'detailText': r(None, _parse_runs, True),
        'detailIcon': r('detail_icon', lambda x: x.get('iconType')),
        'customThumbnail': r('badge_icons', _parse_thumbnails),

        # membership_item
        'headerPrimaryText': r('header_primary_text', _parse_text),
        'headerSubtext': r('header_secondary_text', _parse_text),
        'sponsorPhoto': r('sponsor_icons', _parse_thumbnails),

        # ticker_paid_sticker_item
        'tickerThumbnails': r('ticker_icons', _parse_thumbnails),

        # deleted messages
        'deletedStateMessage': r(None, _parse_runs, True),
        'targetItemId': 'target_message_id',

        'externalChannelId': 'author_id',

        # action buttons
        'actionButton': r('action', _parse_action_button),

        # addBannerToLiveChatCommand
        'text': r(None, _parse_runs, True),
        'viewerIsCreator': 'viewer_is_creator',
        'targetId': 'target_message_id',
        'isStackable': 'is_stackable',
        'backgroundType': 'background_type',

        # removeBannerForLiveChatCommand
        'targetActionId': 'target_message_id',

        # donation_announcement
        'subtext': r(None, _parse_runs, True),

        # tooltip
        'detailsText': r(None, _parse_runs, True),

        # gifts
        'primaryText': r('message', _parse_text),

        'bannerProperties': 'banner_properties',
        'headerOverlayImage': r('header_overlay_image', _parse_thumbnails),
    }

    _COLOUR_KEYS = [
        # paid_message
        'authorNameTextColor', 'timestampColor', 'bodyBackgroundColor',
        'headerTextColor', 'headerBackgroundColor', 'bodyTextColor',
        'textInputBackgroundColor',

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
        'contextMenuAccessibility', 'contextMenuEndpoint', 'trackingParams', 'accessibility', 'dwellTimeMs',

        'empty',  # signals liveChatMembershipItemRenderer has no message body

        'contextMenuButton',

        # parsed elsewhere
        'showItemEndpoint',
        'durationSec',

        # banner parsed elsewhere
        'header', 'contents', 'actionId',

        # tooltipRenderer
        'dismissStrategy', 'suggestedPosition', 'promoConfig'
    ]

    _KNOWN_KEYS = set(list(_REMAPPING.keys()) +
                      _COLOUR_KEYS + _STICKER_KEYS + _KEYS_TO_IGNORE)

    # KNOWN ACTIONS AND MESSAGE TYPES
    _KNOWN_ADD_TICKER_TYPES = {
        'addLiveChatTickerItemAction': [
            'liveChatTickerSponsorItemRenderer',
            'liveChatTickerPaidStickerItemRenderer',
            'liveChatTickerPaidMessageItemRenderer'
        ]
    }

    _KNOWN_ADD_ACTION_TYPES = {
        'addChatItemAction': [
            # message saying Live Chat replay is on
            'liveChatViewerEngagementMessageRenderer',
            'liveChatMembershipItemRenderer',
            'liveChatTextMessageRenderer',
            'liveChatPaidMessageRenderer',
            'liveChatPlaceholderItemRenderer',  # placeholder
            'liveChatDonationAnnouncementRenderer',

            'liveChatPaidStickerRenderer',
            'liveChatModeChangeMessageRenderer',  # e.g. slow mode enabled

            # Gifting
            'liveChatSponsorshipsGiftPurchaseAnnouncementRenderer',  # purchase
            'liveChatSponsorshipsGiftRedemptionAnnouncementRenderer',  # receive

            'liveChatSponsorshipsHeaderRenderer',

            # TODO find examples of:
            # 'liveChatPurchasedProductMessageRenderer',  # product purchased
            # liveChatLegacyPaidMessageRenderer
            # liveChatModerationMessageRenderer
            # liveChatAutoModMessageRenderer

        ]
    }

    _KNOWN_REPLACE_ACTION_TYPES = {
        'replaceChatItemAction': [
            'liveChatPlaceholderItemRenderer',
            'liveChatTextMessageRenderer'
        ]
    }

    # actions that have an 'item'
    _KNOWN_ITEM_ACTION_TYPES = {
        **_KNOWN_ADD_TICKER_TYPES, **_KNOWN_ADD_ACTION_TYPES}

    # [message deleted] or [message retracted]
    _KNOWN_REMOVE_ACTION_TYPES = {
        'removeChatItemAction': [
            'banUser',
        ],
        'removeChatItemByAuthorAction': [
            'banUser',
        ],
        'markChatItemsByAuthorAsDeletedAction': [
            'banUser'  # deletedStateMessage
        ],
        'markChatItemAsDeletedAction': [
            'deletedMessage'  # deletedStateMessage
        ]
    }

    _KNOWN_ADD_BANNER_TYPES = {
        'addBannerToLiveChatCommand': [
            'liveChatBannerRenderer',
            'liveChatBannerHeaderRenderer',
            'liveChatTextMessageRenderer',
        ]
    }

    _KNOWN_REMOVE_BANNER_TYPES = {
        'removeBannerForLiveChatCommand': [
            'removeBanner'  # targetActionId
        ]
    }

    _KNOWN_TOOLTIP_ACTION_TYPES = {
        'showLiveChatTooltipCommand': [
            'tooltipRenderer'
        ]
    }

    # Not come across yet (actions/commands)
    # search "livechat"
    # https://github.com/reachomk/ytvanced/tree/master/src/main/java/com/google/protos/youtube/api/innertube
    # addLiveChatTextMessageFromTemplateAction
    # liveChatMessageBuyFlowHeadingRenderer
    # liveChatPaidMessageFooterRenderer
    # liveChatProductButtonRenderer
    # liveChatPurchaseMessageEndpoint
    # replaceLiveChatRendererAction
    # showLiveChatDialogAction
    # showLiveChatSurveyCommand

    # Not checked for
    # _KNOWN_IGNORE_ACTION_TYPES = {
    #     'authorBadges': [
    #         'liveChatAuthorBadgeRenderer'
    #     ],
    #     'showLiveChatItemEndpoint': [
    #         'liveChatPaidStickerRenderer',
    #         'liveChatPaidMessageRenderer',
    #         'liveChatMembershipItemRenderer'
    #     ]
    # }

    _KNOWN_POLL_ACTION_TYPES = {
    }

    _KNOWN_IGNORE_ACTION_TYPES = {

        # TODO add support for poll actions
        'showLiveChatActionPanelAction': [],
        'updateLiveChatPollAction': [],
        'closeLiveChatActionPanelAction': [],

        'liveChatReportModerationStateCommand': [],

    }

    _KNOWN_ACTION_TYPES = {
        **_KNOWN_ITEM_ACTION_TYPES,
        **_KNOWN_REMOVE_ACTION_TYPES,
        **_KNOWN_REPLACE_ACTION_TYPES,
        **_KNOWN_ADD_BANNER_TYPES,
        **_KNOWN_REMOVE_BANNER_TYPES,
        **_KNOWN_TOOLTIP_ACTION_TYPES,
        **_KNOWN_POLL_ACTION_TYPES,
        **_KNOWN_IGNORE_ACTION_TYPES
    }

    _KNOWN_IGNORE_MESSAGE_TYPES = [
        'liveChatPlaceholderItemRenderer'
    ]
    _KNOWN_MESSAGE_TYPES = []
    for _action in _KNOWN_ACTION_TYPES:
        _KNOWN_MESSAGE_TYPES += _KNOWN_ACTION_TYPES[_action]

    _KNOWN_SEEK_CONTINUATIONS = [
        'playerSeekContinuationData'
    ]

    _KNOWN_CHAT_CONTINUATIONS = [
        'invalidationContinuationData', 'timedContinuationData',
        'liveChatReplayContinuationData', 'reloadContinuationData'
    ]

    _KNOWN_CONTINUATIONS = _KNOWN_SEEK_CONTINUATIONS + _KNOWN_CHAT_CONTINUATIONS

    def generate_urls(self, **kwargs):
        items = self._get_testing_items()

        for item in items:
            yield self._YT_VIDEO_TEMPLATE.format(item['video_id'])

    _LIVE_PLAYLIST_URL = _YT_HOME + '/channel/UC4R8DWoMoI7CAwX8_LjQHig'

    def _get_testing_items(self):
        params = {
            'max_attempts': 10
        }

        yt_initial_data, ytcfg, player_response_info = self._get_initial_info(
            self._LIVE_PLAYLIST_URL, params)

        sections = yt_initial_data['contents']['twoColumnBrowseResultsRenderer']['tabs'][
            0]['tabRenderer']['content']['sectionListRenderer']['contents']

        for section in sections:
            section_info = section['itemSectionRenderer']['contents'][0]['shelfRenderer']

            playlist_url = self._YT_HOME + \
                section_info['endpoint']['commandMetadata']['webCommandMetadata']['url']

            yield from self.get_playlist_items(playlist_url)

    @staticmethod
    def _get_rendered_content(yt_info, tab_index=0):
        return yt_info['contents']['twoColumnBrowseResultsRenderer']['tabs'][tab_index]['tabRenderer']['content'][
            'sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents'][0]

    _VIDEO_REMAPPING = {
        'videoId': 'video_id',
        'title': r('title', lambda x: YouTubeChatDownloader._parse_runs(x)['message']),
        'videoType': 'video_type',
        'viewCountText': r('view_count', lambda x: YouTubeChatDownloader._parse_text(x)),
        'shortViewCountText': r('short_view_count', lambda x: YouTubeChatDownloader._parse_text(x)),

        # 'videoId', 'thumbnail', 'title', 'viewCountText', 'navigationEndpoint', 'ownerBadges', 'trackingParams', 'shortViewCountText', 'menu', 'thumbnailOverlays'
    }

    @staticmethod
    def _parse_video(video_renderer):
        # Get video type:
        # One of DEFAULT, UPCOMING, LIVE
        video_type = 'DEFAULT'
        thumbnail_overlays = multi_get(
            video_renderer, 'thumbnailOverlays') or []
        for thumbnail_overlay in thumbnail_overlays:
            video_type = multi_get(
                thumbnail_overlay, 'thumbnailOverlayTimeStatusRenderer', 'style')
            if video_type:
                break

        video_renderer['videoType'] = video_type

        return r.remap_dict(video_renderer, YouTubeChatDownloader._VIDEO_REMAPPING)

    _VIDEO_TYPE_REMAPPING = {
        # Name : url component
        'videos': 'videos',
        'shorts': 'shorts',
        'live': 'streams',
    }

    def get_user_videos(self, channel_id=None, user_id=None, custom_username=None, handle=None, video_type='videos', params=None):
        """Retrieve all videos listed on the user's channel

        If more than one of `channel_id`, `user_id` and `custom_username`
        are specifed, the first one specified will be returned.

        :param channel_id: The user's channel ID, defaults to None.
            (e.g., https://www.youtube.com/channel/<channel_id>)
        :type channel_id: str, optional
        :param user_id: The user's ID, defaults to None
            (e.g., https://www.youtube.com/user/<user_id>)
        :type user_id: str, optional
        :param custom_username: User's custom username, defaults to None
            (e.g., https://www.youtube.com/c/<custom_username>)
        :type custom_username: str, optional
        :param handle: User's handle, defaults to None
            (e.g., https://www.youtube.com/@<handle>)
        :type handle: str, optional
        :param video_type: Determines which videos will be retrieved, defaults to 'videos'.
            Must be one of 'videos', 'live', or 'shorts'.
        :type video_type: str, optional
        :param params: Additional program parameters, defaults to None
        :type params: dict, optional
        :raises ValueError: If no user is specified or an invalid video_type is specified
        :raises UserNotFound: If the user cannot be found
        :raises NoVideos: If the channel has no videos
        :yield: The next video
        :rtype: dict
        """

        _id = ''
        _type = ''
        if channel_id:
            _id = channel_id
            _type = 'channel/'
        elif user_id:
            _id = user_id
            _type = 'user/'
        elif custom_username:
            _id = custom_username
            _type = 'c/'
        elif handle:
            _id = handle
            _type = '@'
        else:
            raise ValueError('No user type specified.')

        video_type = video_type.lower()
        vid_type = self._VIDEO_TYPE_REMAPPING.get(video_type)

        if not vid_type:
            raise ValueError(
                f'Invalid argument passed for video_type. Must be one of {set(self._VIDEO_TYPE_REMAPPING.keys())}')

        user_url = f'https://www.youtube.com/{_type}{_id}'
        yt_info, ytcfg, _ = self._get_initial_info(
            f'{user_url}/{vid_type}', params)

        tabs = multi_get(yt_info, 'contents',
                         'twoColumnBrowseResultsRenderer', 'tabs')
        if not tabs:
            raise UserNotFound(f'Unable to find user: "{user_url}"')

        page_contents = None
        for tab in tabs:
            tab_data = tab.get('tabRenderer', {})
            if not tab_data or not tab_data.get('selected'):
                continue

            tab_title = tab_data.get('title', '').lower()
            # Check that the returned grid is what was asked for
            # YouTube tries to correct your mistake by selecting the home tab
            # if you try to access a tab that is not visible.
            if tab_title != video_type.lower():
                log('debug',
                    f'"{tab_title}" tab is not visible for this channel (i.e. there are no such videos).')
                raise NoVideos(
                    f'This channel has no videos of the requested type ({video_type}).')

            page_contents = tab_data.get('content')

        api_key = ytcfg.get('INNERTUBE_API_KEY')
        continuation_url = self._YOUTUBE_BROWSE_API_TEMPLATE.format(api_key)

        # innertube_context =
        # print('innertube_context', innertube_context)
        continuation_params = {
            'context': ytcfg.get('INNERTUBE_CONTEXT') or {}
        }
        continuation = None
        first_time = True
        while True:
            if first_time:
                items = multi_get(
                    page_contents, 'richGridRenderer', 'contents')
                first_time = False
            else:
                continuation_params['continuation'] = continuation
                yt_info = self._get_continuation_info(
                    continuation_url, params, json=continuation_params)
                items = multi_get(yt_info, 'onResponseReceivedActions',
                                  0, 'appendContinuationItemsAction', 'continuationItems')

            if not items:
                break

            continuation = None
            for item in items:
                vid = multi_get(item, 'richItemRenderer',
                                'content', 'videoRenderer')
                continuation_item = item.get('continuationItemRenderer')

                if vid:
                    yield self._parse_video(vid)
                elif continuation_item:
                    continuation = multi_get(
                        continuation_item, 'continuationEndpoint', 'continuationCommand', 'token')

            if not continuation:
                break

    def get_playlist_items(self, playlist_url, params=None):

        yt_initial_data, ytcfg, _ = self._get_initial_info(
            playlist_url, params)

        page_contents = self._get_rendered_content(yt_initial_data)

        # TODO remove code duplication
        api_key = ytcfg.get('INNERTUBE_API_KEY')
        continuation_url = self._YOUTUBE_BROWSE_API_TEMPLATE.format(api_key)

        continuation_params = {
            'context': ytcfg.get('INNERTUBE_CONTEXT') or {}
        }
        continuation = None
        first_time = True
        while True:
            if first_time:
                items = multi_get(
                    page_contents, 'playlistVideoListRenderer', 'contents')
                first_time = False
            else:
                continuation_params['continuation'] = continuation
                yt_info = self._get_continuation_info(
                    continuation_url, params, json=continuation_params)
                items = multi_get(yt_info, 'onResponseReceivedActions',
                                  0, 'appendContinuationItemsAction', 'continuationItems')

            if not items:
                break

            continuation = None
            for item in items:
                vid = item.get('playlistVideoRenderer')
                continuation_item = item.get('continuationItemRenderer')

                if vid:
                    yield self._parse_video(vid)
                elif continuation_item:
                    continuation = multi_get(
                        continuation_item, 'continuationEndpoint', 'continuationCommand', 'token')

            if not continuation:
                break

    _CONSENT_ID_REGEX = r'PENDING\+(\d+)'
    # https://github.com/ytdl-org/youtube-dl/blob/a8035827177d6b59aca03bd717acb6a9bdd75ada/youtube_dl/extractor/youtube.py#L251

    def _initialize_consent(self):
        if self.get_cookie_value('__Secure-3PSID'):
            return

        consent_id = None
        consent = self.get_cookie_value('CONSENT')

        if consent:
            if 'YES' in consent:
                return

            consent_id = regex_search(consent, self._CONSENT_ID_REGEX)

        if not consent_id:
            consent_id = random.randint(100, 999)

        self.set_cookie_value('.youtube.com', 'CONSENT',
                              f'YES+cb.20210328-17-p0.en+FX+{consent_id}')

    def _generate_sapisidhash_header(self):
        sapis_id = self.get_cookie_value('SAPISID')
        sapisid_cookie = self.get_cookie_value('__Secure-3PAPISID') or sapis_id

        if sapisid_cookie is None:
            return

        time_now = round(time.time())

        # SAPISID cookie is required if not already present
        if not sapis_id:
            self.set_cookie_value(
                '.youtube.com', 'SAPISID', sapisid_cookie, secure=True, expire_time=time_now + 3600)

        # SAPISIDHASH algorithm from https://stackoverflow.com/a/32065323
        sapisidhash = hashlib.sha1(
            f'{time_now} {sapisid_cookie} {self._YT_HOME}'.encode('utf-8')).hexdigest()
        return f'SAPISIDHASH {time_now}_{sapisidhash}'

    def _get_continuation_info(self, continuation_url, program_params, **post_kwargs):
        if program_params is None:
            program_params = {}
        max_attempts = program_params.get('max_attempts', 1)

        for attempt_number in attempts(max_attempts):
            try:
                response = self._session_post(continuation_url, **post_kwargs)
                json_response = response.json()

                # Check for errors:
                error = json_response.get('error')
                if error:
                    error_code = error.get('code')
                    error_message = error.get('message')

                    if error_code // 100 == 5:  # Server error, retry
                        self.retry(attempt_number,
                                   text=error_message, **program_params)
                        continue
                    # 404 means deleted while live

                return json_response

            except JSONDecodeError as e:
                self.retry(attempt_number, error=e, **program_params,
                           text=f'Unable to parse JSON: `{response.text}`')

            except RequestException as e:
                self.retry(attempt_number, error=e, **program_params)

    def _get_initial_info(self, url, params=None):
        if params is None:
            params = {}

        max_attempts = params.get('max_attempts', 1)
        for attempt_number in attempts(max_attempts):
            try:
                response = self._session_get(url)
                html = response.text
                yt = regex_search(html, self._YT_INITIAL_DATA_RE)
                yt_initial_data = try_parse_json(yt)

                if response.status_code != 200:
                    # Check for errors
                    title = get_title_of_webpage(html)
                    if response.status_code == 404:
                        raise VideoNotFound(title)
                    elif response.status_code // 100 == 5:  # Server error, retry
                        self.retry(attempt_number, text=title, **params)
                        continue

                if not yt_initial_data:  # Fatal error
                    log('debug', html)
                    raise ParsingError(f'Unable to parse initial video data')

                cfg = regex_search(html, self._YT_CFG_RE)
                ytcfg = try_parse_json(cfg, {})

                player_response = regex_search(
                    html, self._YT_INITIAL_PLAYER_RESPONSE_RE)

                player_response_info = try_parse_json(player_response, {})

                return yt_initial_data, ytcfg, player_response_info

            except RequestException as e:
                self.retry(attempt_number, error=e, **params)

        return None, None, None

    def get_video_data(self, video_id, params=None):
        return self._parse_video_data(video_id, params)[0]

    def _parse_video_data(self, video_id, params=None, video_type='video'):
        details = {}

        if video_type == 'clip':
            original_url = self._YT_CLIP_TEMPLATE.format(video_id)
        else:  # video_type == 'video'
            original_url = self._YT_VIDEO_TEMPLATE.format(video_id)

        yt_initial_data, ytcfg, player_response_info = self._get_initial_info(
            original_url, params)

        if not player_response_info:
            log('debug', yt_initial_data)
            log('warning', f'Unable to parse player response, proceeding with caution')

        streaming_data = player_response_info.get('streamingData') or {}
        first_format = multi_get(streaming_data, 'adaptiveFormats', 0) or multi_get(
            streaming_data, 'formats', 0) or {}

        # Live streaming details
        player_renderer = multi_get(
            player_response_info, 'microformat', 'playerMicroformatRenderer') or {}
        live_details = player_renderer.get('liveBroadcastDetails') or {}

        # Video info
        video_details = player_response_info.get('videoDetails') or {}
        details['title'] = video_details.get('title')
        details['author'] = video_details.get('author')
        details['author_id'] = video_details.get('channelId')
        details['original_video_id'] = video_details.get('videoId')

        # Clip info
        clip_details = player_response_info.get('clipConfig')
        if clip_details:
            details['clip_start_time'] = (float_or_none(
                clip_details.get('startTimeMs', 0)) / 1e3)
            details['clip_end_time'] = (float_or_none(
                clip_details.get('endTimeMs', 0)) / 1e3)
            details['video_type'] = 'clip'

        elif not video_details.get('isLiveContent'):
            details['video_type'] = 'premiere'

        else:
            details['video_type'] = 'video'

        start_timestamp = live_details.get('startTimestamp')
        end_timestamp = live_details.get('endTimestamp')
        details['start_time'] = parse_iso8601(
            start_timestamp) if start_timestamp else None
        details['end_time'] = parse_iso8601(
            end_timestamp) if end_timestamp else None

        details['duration'] = (float_or_none(first_format.get('approxDurationMs', 0)) / 1e3) or float_or_none(
            video_details.get('lengthSeconds')) or float_or_none(player_renderer.get('lengthSeconds'))

        if not details['duration'] and details['start_time'] and details['end_time']:
            details['duration'] = (
                details['end_time'] - details['start_time'])/1e6

        # Parse continuation info
        sub_menu_items = multi_get(yt_initial_data, 'contents', 'twoColumnWatchNextResults', 'conversationBar', 'liveChatRenderer',
                                   'header', 'liveChatHeaderRenderer', 'viewSelector', 'sortFilterSubMenuRenderer', 'subMenuItems') or {}
        details['continuation_info'] = {
            x['title']: x['continuation']['reloadContinuationData']['continuation']
            for x in sub_menu_items
        }

        # live, upcoming or past
        if video_details.get('isLive') or live_details.get('isLiveNow'):
            details['status'] = 'live'

        elif video_details.get('isUpcoming'):
            details['status'] = 'upcoming'

        else:
            details['status'] = 'past'

        return details, player_response_info, yt_initial_data, ytcfg

    def _get_initial_video_info(self, video_id, params=None, video_type='video'):
        """ Get initial YouTube video information. """

        details, player_response_info, yt_initial_data, ytcfg = self._parse_video_data(
            video_id, params, video_type)

        # Error checking
        if not details['continuation_info']:
            # Only raise an error if there is no continuation info. Sometimes you
            # are able to view chat, but not the video (e.g. for very long livestreams)
            playability_status = player_response_info.get(
                'playabilityStatus') or {}
            error_screen = playability_status.get('errorScreen')
            if error_screen:  # There is a error screen visible
                error_reasons = {
                    'reason': '',
                    'subreason': '',
                }
                error_info = try_get_first_value(error_screen)

                for error_reason in error_reasons:
                    text = error_info.get(error_reason) or {}

                    error_reasons[error_reason] = text.get('simpleText') or self._parse_runs(
                        text, False)['message'] or error_info.pop(
                        'itemTitle', '') or error_info.pop(
                            'offerDescription', '') or playability_status.get(error_reason) or ''

                error_message = ''
                for error_reason in error_reasons:
                    if error_reasons[error_reason]:
                        if isinstance(error_reasons[error_reason], str):
                            error_message += f" {error_reasons[error_reason].rstrip('.')}."
                        else:
                            error_message += str(error_reasons[error_reason])

                error_message = error_message.strip()

                status = playability_status.get('status')

                if status == 'ERROR':
                    raise VideoUnavailable(error_message)
                elif status == 'LOGIN_REQUIRED':
                    raise LoginRequired(error_message)
                elif status == 'UNPLAYABLE':
                    raise VideoUnplayable(error_message)
                elif status == 'LIVE_STREAM_OFFLINE':
                    raise ChatDisabled(error_message)
                else:
                    log('debug',
                        f'Unknown playability status: {status}. {playability_status}')
                    error_message = f'{status}: {error_message}'
                    raise VideoUnavailable(error_message)

            # Check for pop up
            popup_info = multi_get(yt_initial_data, 'onResponseReceivedActions',
                                   0, 'openPopupAction', 'popup', 'confirmDialogRenderer')
            if popup_info:
                error_message = multi_get(popup_info, 'title', 'simpleText')
                dialog_messages = multi_get(popup_info, 'dialogMessages') or []
                error_message += '. ' + \
                    ' '.join(map(lambda x: x.get('simpleText'), dialog_messages))
                raise VideoUnavailable(error_message)
            elif not yt_initial_data.get('contents'):
                log('debug', f'Initial YouTube data: {yt_initial_data}')
                raise VideoUnavailable(
                    'Unable to find initial video contents.')
            else:
                # Video exists, but you cannot view chat for some reason
                error_runs = multi_get(yt_initial_data, 'contents', 'twoColumnWatchNextResults', 'conversationBar',
                                       'conversationBarRenderer', 'availabilityMessage', 'messageRenderer', 'text')
                error_message = self._parse_runs(error_runs, False)[
                    'message'] if error_runs else 'Video does not have a chat replay.'

                # Live chat replay was turned off for this video. -> NoChatReplay
                if 'disabled' in error_message:
                    raise ChatDisabled(error_message)
                else:
                    raise NoChatReplay(error_message)

        return details, ytcfg

    def _extract_account_syncid(self, ytcfg):
        sync_ids = ytcfg.get('DATASYNC_ID').split('||')
        if len(sync_ids) >= 2 and sync_ids[1]:
            # datasyncid is of the form "channel_syncid||user_syncid" for secondary channel
            # and just "user_syncid||" for primary channel. We only want the channel_syncid
            return sync_ids[0]

        # ytcfg includes channel_syncid if on secondary channel
        return ytcfg.get('DELEGATED_SESSION_ID')

    def _generate_headers(self, ytcfg):
        headers = {
            'origin': self._YT_HOME,
            'x-youtube-client-name': str(ytcfg.get('INNERTUBE_CONTEXT_CLIENT_NAME')),
            'x-youtube-client-version': str(ytcfg.get('INNERTUBE_CLIENT_VERSION')),
            'x-origin': self._YT_HOME,
            'x-goog-authuser': '0'
        }

        identity_token = ytcfg.get('ID_TOKEN')
        if identity_token:
            headers['x-youtube-identity-token'] = identity_token

        account_syncid = self._extract_account_syncid(ytcfg)
        if account_syncid:
            headers['x-goog-pageid'] = account_syncid

        session_index = ytcfg.get('SESSION_INDEX')
        if account_syncid or session_index:
            headers['x-goog-authuser'] = session_index or 0

        visitor_data = multi_get(
            ytcfg, 'INNERTUBE_CONTEXT', 'client', 'visitorData')
        if visitor_data:
            headers['x-goog-visitor-id'] = visitor_data

        auth = self._generate_sapisidhash_header()
        if auth:
            headers['authorization'] = auth

        return headers

    def _get_chat_messages(self, initial_info, ytcfg, params):

        initial_continuation_info = initial_info.get('continuation_info') or {}
        if len(initial_continuation_info) < 2:
            raise NoContinuation(
                f'Initial continuation information could not be found: {initial_info}')

        status = initial_info.get('status')

        # duration = initial_info.get('duration')
        # stream_start_time = initial_info.get('start_time')
        offset = initial_info.get('offset')  # Clips

        start_time = ensure_seconds(params.get('start_time'))
        end_time = ensure_seconds(params.get('end_time'))

        # Top chat replay - Some messages, such as potential spam, may not be visible
        # Live chat replay - All messages are visible
        chat_type = params.get('chat_type', 'live').title()  # Live or Top
        continuation_index = 0 if chat_type == 'Top' else 1
        continuation_info = list(initial_continuation_info.items())[
            continuation_index]
        continuation = continuation_info[1]
        log('debug', f'Getting {chat_type} chat ({continuation_info[0]}).')

        is_replay = status == 'past'

        api_type = 'live_chat'
        if is_replay:
            api_type += '_replay'

        init_page = self._YOUTUBE_INIT_API_TEMPLATE.format(
            api_type, continuation)

        api_key = ytcfg.get('INNERTUBE_API_KEY')

        continuation_url = self._YOUTUBE_CHAT_API_TEMPLATE.format(
            api_type, api_key)
        offset_milliseconds = (
            start_time * 1000) if isinstance(start_time, (float, int)) else None

        # force_no_timeout = params.get('force_no_timeout')

        max_attempts = params.get('max_attempts')

        messages_groups_to_add = params.get('message_groups') or []
        messages_types_to_add = params.get('message_types') or []

        invalid_groups = set(messages_groups_to_add) - \
            self._MESSAGE_GROUPS.keys()
        if 'all' not in messages_groups_to_add and invalid_groups:
            raise InvalidParameter(
                f'Invalid groups specified: {invalid_groups}')

        self.check_for_invalid_types(
            messages_types_to_add, self._MESSAGE_TYPES)

        # Generate base headers and update session headers
        self.update_session_headers(self._generate_headers(ytcfg))

        self.update_session_headers({
            'content-type': 'application/json',
            'referer': init_page
        })

        innertube_context = ytcfg.get('INNERTUBE_CONTEXT') or {}

        message_count = 0
        first_time = True
        click_tracking_params = None

        while True:
            continuation_params = {
                'context': innertube_context,
                'continuation': continuation
            }

            # Update authentication header, if necessary
            auth = self._generate_sapisidhash_header()
            if auth:
                self.update_session_headers({
                    'authorization': auth
                })

            if first_time:
                # must run to get first few messages, otherwise might miss some
                yt_info = self._get_initial_info(init_page, params)[0]

            else:
                if is_replay and offset_milliseconds is not None:
                    continuation_params['currentPlayerState'] = {
                        'playerOffsetMs': offset_milliseconds}

                if click_tracking_params:
                    continuation_params['context']['clickTracking'] = {
                        'clickTrackingParams': click_tracking_params}

                yt_info = self._get_continuation_info(
                    continuation_url, params, json=continuation_params)

            debug_info = {
                'click_tracking': multi_get(continuation_params, 'context', 'clickTracking'),
                'continuation': multi_get(continuation_params, 'continuation')
            }
            log('debug', [
                f'Continuation parameters: {debug_info}',
                f"Session headers: {', '.join(self.session.headers.keys())}"
            ])

            logged_in_info = multi_get(
                yt_info, 'responseContext', 'serviceTrackingParams', 1, 'params', 0)
            log('debug', f'Logged-in info: {logged_in_info}')

            info = multi_get(yt_info, 'continuationContents',
                             'liveChatContinuation')
            if not info:
                log('debug', f'No continuation information found: {yt_info}')
                return

            actions = info.get('actions') or []

            if actions:
                for action in actions:
                    data = {}

                    # if it is a replay chat item action, must re-base it
                    replay_chat_item_action = action.get(
                        'replayChatItemAction')
                    if replay_chat_item_action:
                        offset_time = replay_chat_item_action.get(
                            'videoOffsetTimeMsec')
                        if offset_time:
                            data['time_in_seconds'] = float(offset_time) / 1000

                        action = replay_chat_item_action['actions'][0]

                    action.pop('clickTrackingParams', None)
                    original_action_type = try_get_first_key(action)

                    data['action_type'] = camel_case_split(
                        remove_suffixes(original_action_type, ('Action', 'Command')))

                    original_message_type = None
                    original_item = {}

                    # We now parse the info and get the message
                    # type based on the type of action
                    if original_action_type in self._KNOWN_ITEM_ACTION_TYPES:
                        original_item = multi_get(
                            action, original_action_type, 'item')

                        original_message_type = try_get_first_key(
                            original_item)
                        data = self._parse_item(original_item, data, offset)

                    elif original_action_type in self._KNOWN_REMOVE_ACTION_TYPES:
                        original_item = action
                        if original_action_type == 'markChatItemAsDeletedAction':
                            original_message_type = 'deletedMessage'
                        else:  # markChatItemsByAuthorAsDeletedAction, removeChatItemAction
                            original_message_type = 'banUser'

                        data = self._parse_item(original_item, data, offset)

                    elif original_action_type in self._KNOWN_REPLACE_ACTION_TYPES:
                        original_item = multi_get(
                            action, original_action_type, 'replacementItem')
                        original_message_type = try_get_first_key(
                            original_item)
                        data = self._parse_item(original_item, data, offset)

                    elif original_action_type in self._KNOWN_TOOLTIP_ACTION_TYPES:
                        original_item = multi_get(
                            action, original_action_type, 'tooltip')
                        original_message_type = try_get_first_key(
                            original_item)
                        data = self._parse_item(original_item, data, offset)

                    elif original_action_type in self._KNOWN_ADD_BANNER_TYPES:
                        original_item = multi_get(
                            action, original_action_type, 'bannerRenderer')

                        if original_item:
                            original_message_type = try_get_first_key(
                                original_item)
                            contents = original_item[original_message_type].get(
                                'contents')
                            parsed_contents = self._parse_item(
                                contents, offset=offset)

                            data.update(parsed_contents)

                        else:
                            debug_log(
                                'No bannerRenderer item',
                                f'Action type: {original_action_type}',
                                f'Action: {action}',
                                f'Parsed data: {data}'
                            )

                    elif original_action_type in self._KNOWN_REMOVE_BANNER_TYPES:
                        original_item = action
                        original_message_type = 'removeBanner'
                        data = self._parse_item(original_item, data, offset)

                    elif original_action_type in self._KNOWN_IGNORE_ACTION_TYPES:
                        continue  # ignore these

                    else:
                        # not processing these
                        debug_log(
                            f'Unknown action: {original_action_type}',
                            action,
                            data
                        )

                    test_for_missing_keys = original_item.get(
                        original_message_type, {}).keys()
                    missing_keys = test_for_missing_keys - self._KNOWN_KEYS

                    if not data:
                        debug_log(
                            f'Parse of action returned empty results: {original_action_type}',
                            action
                        )

                    if missing_keys:
                        debug_log(
                            f'Missing keys found: {missing_keys}',
                            f'Message type: {original_message_type}',
                            f'Action type: {original_action_type}',
                            f'Action: {action}',
                            f'Parsed data: {data}'
                        )

                    if original_message_type:

                        new_index = remove_prefixes(
                            original_message_type, 'liveChat')
                        new_index = remove_suffixes(new_index, 'Renderer')
                        data['message_type'] = camel_case_split(new_index)

                        # TODO add option to keep placeholder items
                        if original_message_type in self._KNOWN_IGNORE_MESSAGE_TYPES:
                            continue
                            # skip placeholder items
                        elif original_message_type not in self._KNOWN_ACTION_TYPES[original_action_type]:
                            debug_log(
                                f'Unknown message type "{original_message_type}" for action "{original_action_type}"',
                                f"New message type: {data['message_type']}",
                                f'Action: {action}',
                                f'Parsed data: {data}'
                            )

                    else:  # no type # can ignore message
                        debug_log(
                            'No message type',
                            f'Action type: {original_action_type}',
                            f'Action: {action}',
                            f'Parsed data: {data}'
                        )
                        continue

                    # check whether to skip this message or not, based on its type

                    to_add = self._must_add_item(
                        data,
                        self._MESSAGE_GROUPS,
                        messages_groups_to_add,
                        messages_types_to_add
                    )

                    if not to_add:
                        continue

                    # if from a replay, check whether to skip this message or not, based on its time
                    if is_replay:
                        # assume message is at beginning if it does not have a time component
                        time_in_seconds = data.get(
                            'time_in_seconds', 0) + (offset or 0)

                        before_start = start_time is not None and time_in_seconds < start_time
                        after_end = end_time is not None and time_in_seconds > end_time

                        if first_time and before_start:
                            continue  # first time and invalid start time
                        elif before_start or after_end:
                            return  # while actually searching, if time is invalid

                    # try to reconstruct time in seconds from timestamp and stream start
                    # if data.get('time_in_seconds') is None and data.get('timestamp') and stream_start_time:
                    #     data['time_in_seconds'] = (data['timestamp'] - stream_start_time)/1e6
                    #     data['time_text'] = seconds_to_time(int(data['time_in_seconds']))

                    message_count += 1
                    yield data

                log('debug', f'Total number of messages: {message_count}')
            elif is_replay:
                # no more actions to process in a chat replay
                break
            else:
                # otherwise, is live, so keep trying
                log('debug', 'No actions to process.')

            # assume there are no more chat continuations
            no_continuation = True

            # parse the continuation information
            for cont in info.get('continuations') or []:

                continuation_key = try_get_first_key(cont)
                continuation_info = cont[continuation_key]

                log('debug', f'Continuation info: {continuation_info}')

                if continuation_key in self._KNOWN_CHAT_CONTINUATIONS:

                    # set new chat continuation
                    # overwrite if there is continuation data
                    continuation = continuation_info.get('continuation')

                    click_tracking_params = continuation_info.get(
                        'clickTrackingParams') or continuation_info.get('trackingParams')
                    # there is a chat continuation
                    no_continuation = False

                elif continuation_key in self._KNOWN_SEEK_CONTINUATIONS:
                    pass
                    # ignore these continuations

                else:
                    debug_log(
                        f'Unknown continuation: {continuation_key}',
                        cont
                    )

                # sometimes continuation contains timeout info
                sleep_duration = continuation_info.get('timeoutMs')
                # and not actions:# and not force_no_timeout:
                if sleep_duration:
                    # Timeouts help prevent 429 errors (caused by too many requests).
                    #
                    # A single request to the YouTube live chat endpoint seems to only
                    # go back around 10 seconds (only retrieving around 150-200 messages
                    # at any given time).
                    #
                    # For very large livestreams, YouTube sometimes sets timeouts to be
                    # more than 10 seconds (most likely to alleviate server stress).
                    # This means that, normally, users will not be able to see all chat
                    # messages (leaving a gap of timeout - 10 seconds).
                    #
                    # To get around this, we clamp the timeout to be between 0 and 8000
                    # milliseconds (a 2 second window for making the next request).
                    # This ensures that no messages are missed and we do spam YouTube
                    # with requests (which may lead to 429 errors or IP blocking).

                    sleep_duration = max(min(sleep_duration, 8000), 0)

                    log('debug', f'Sleeping for {sleep_duration}ms.')
                    interruptible_sleep(sleep_duration / 1000)

            if no_continuation:  # no continuation, end
                break

            if first_time:
                first_time = False

    def _get_chat_by_clip_id(self, match, params):
        return self.get_chat_by_clip_id(match.group('id'), params)

    def get_chat_by_clip_id(self, clip_id, params):

        initial_info, ytcfg = self._get_initial_video_info(
            clip_id, params, video_type='clip')

        initial_info['offset'] = clip_start_time = initial_info.get(
            'clip_start_time')
        clip_end_time = initial_info.get('clip_end_time')

        max_duration = clip_end_time - clip_start_time

        params['start_time'] = ensure_seconds(
            params.get('start_time'), 0) + clip_start_time
        params['end_time'] = ensure_seconds(params.get(
            'end_time'), max_duration) + clip_start_time

        return Chat(
            self._get_chat_messages(initial_info, ytcfg, params),
            id=clip_id,
            **initial_info
        )

    def _get_chat_by_user(self, match, params):
        match_id = match.group('id')
        user_type = match.group('type') or ''
        user_type = user_type.rstrip('/')  # channel|c|user|@|

        if user_type == 'channel':
            return self.get_chat_by_channel_id(match_id, params)

        elif user_type == 'user':
            return self.get_chat_by_user_id(match_id, params)

        elif user_type in ('c', ''):
            return self.get_chat_by_custom_username(match_id, params)

        elif user_type == '@':
            return self.get_chat_by_handle(match_id, params)

        else:
            raise ValueError(f'Invalid user_type: {user_type}')

    def get_chat_by_channel_id(self, channel_id, params):
        return self._get_chat_by_user_args({
            'channel_id': channel_id
        }, params)

    def get_chat_by_user_id(self, user_id, params):
        """
        Such as NASAtelevision in https://www.youtube.com/user/NASAtelevision

        :param user_id:
        :type user_id: [type]
        """
        return self._get_chat_by_user_args({
            'user_id': user_id
        }, params)

    def get_chat_by_custom_username(self, custom_username, params):
        return self._get_chat_by_user_args({
            'custom_username': custom_username
        }, params)

    def get_chat_by_handle(self, handle, params):
        return self._get_chat_by_user_args({
            'handle': handle
        }, params)

    def _get_chat_by_user_args(self, user_video_args, params):
        # TODO add param for wait time
        # params['exit_on_fail'] = True

        title = try_get_first_value(user_video_args)
        chat_item = Chat(title=title, id=title)  # Create empty chat object
        chat_item.chat = self._get_chat_messages_by_user_args(
            user_video_args, chat_item, params)

        return chat_item

    def _get_chat_messages_by_user_args(self, user_video_args, chat_item, params):
        # chat_item allows to change title and info based on new info

        list_of_vids_to_ignore = params.get('ignore') or []

        sleep_amount = 30  # params.get('retry_timeout')
        # For efficiency purposes, do not loop over all past broadcasts if not found
        max_vids_to_try = 5

        while True:

            vids = self.get_user_videos(
                **user_video_args, video_type='live', params=params)

            for video in islice(vids, max_vids_to_try):
                video_id = video['video_id']

                if video['video_type'] not in ('LIVE', 'UPCOMING'):
                    log('debug',
                        f'Skipping video with ID: "{video_id}" (not live/upcoming)')
                    continue

                if video_id in list_of_vids_to_ignore:
                    log('debug', f'Skipping video with ID: "{video_id}"')
                    continue

                try:
                    chat = self.get_chat_by_video_id(video_id, params)

                    log('info',
                        f"Found a livestream: \"{video['title']}\" ({video_id}).")

                    for key, value in vars(chat).items():  # Update chat item
                        if key != 'chat' and not key.startswith('_'):
                            setattr(chat_item, key, value)

                    yield from chat
                    break

                except ChatDownloaderError as e:
                    # For some reason, doesn't work
                    log('warning',
                        f"Unable to get chat for \"{video['title']}\" ({video_id}) due to an error: \"{e}\"")

            log('info',
                f'There are no active or upcoming livestreams with a live chat. Retrying in {sleep_amount} seconds.')
            interruptible_sleep(sleep_amount)

            # continue forever, until reaching a video with valid chat

    def get_chat_by_video_id(self, video_id, params):
        """Get chat messages for a YouTube video, given its ID.

        :param video_id: YouTube video ID
        :type video_id: str
        :return: Chat object for the corresponding YouTube video
        :rtype: Chat
        """
        initial_info, ytcfg = self._get_initial_video_info(video_id, params)

        return Chat(
            self._get_chat_messages(initial_info, ytcfg, params),
            id=video_id,
            **initial_info
        )

    def _get_chat_by_video_id(self, match, params):
        return self.get_chat_by_video_id(match.group('id'), params)
