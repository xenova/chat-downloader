
from .common import (
    BaseChatDownloader,
    Chat,
    Remapper as r,
    Image
)

from ..errors import (
    ChatDownloaderError,
    NoChatReplay,
    NoContinuation,
    ParsingError,
    VideoUnavailable,
    LoginRequired,
    VideoUnplayable,
    InvalidParameter,
    UserNotFound,
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
    try_parse_json
)

from ..debugging import log

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
                'url': 'https://www.youtube.com/watch?v=5qap5aO4i9A',
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
            'name': 'Get messages from top chat replay',
            'params': {
                'url': 'https://www.youtube.com/watch?v=zVCs9Cug_qM',
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
        {
            # 874:24:05 current test
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
                'error': NoChatReplay,
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
        }
    ]

    _YT_INITIAL_BOUNDARY_RE = r'\s*(?:var\s+meta|</script|\n)'
    _YT_INITIAL_DATA_RE = r'(?:window\s*\[\s*["\']ytInitialData["\']\s*\]|ytInitialData)\s*=\s*({.+?})\s*;' + \
        _YT_INITIAL_BOUNDARY_RE
    _YT_INITIAL_PLAYER_RESPONSE_RE = r'ytInitialPlayerResponse\s*=\s*({.+?})\s*;' + \
        _YT_INITIAL_BOUNDARY_RE
    _YT_CFG_RE = r'ytcfg\.set\s*\(\s*({.+?})\s*\)\s*;'

    _YT_HOME = 'https://www.youtube.com'
    _YT_VIDEO_TEMPLATE = _YT_HOME + '/watch?v={}'

    _YOUTUBE_INIT_API_TEMPLATE = _YT_HOME + '/{}?continuation={}'
    _YOUTUBE_CHAT_API_TEMPLATE = _YT_HOME + '/youtubei/v1/live_chat/get_{}?key={}'

    _MESSAGE_GROUPS = {
        'messages': [
            'text_message'  # normal message
        ],
        'superchat': [
            # superchat messages which appear in chat
            'membership_item',
            'paid_message',
            'paid_sticker',
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


        # while this does match 'watch' urls, it will never
        # return this since the above regex is run before this
        '_get_chat_by_user': r'''(?x)
                (?:https?://|//)
                    (?:\w+\.)?
                    (?:
                        youtube(?:kids)?\.com
                    )/
                    (?:
                        (?P<type>channel|c|user)/
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

    @ staticmethod
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

    @ staticmethod
    def _parse_navigation_endpoint(navigation_endpoint, default_text=''):
        try:
            return YouTubeChatDownloader._parse_youtube_link(
                navigation_endpoint['commandMetadata']['webCommandMetadata']['url'])
        except Exception:
            return default_text

    @ staticmethod
    def _parse_header_text(info):
        return YouTubeChatDownloader._parse_runs(info)['message'] or YouTubeChatDownloader._get_simple_text(info)

    @ staticmethod
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

                name = multi_get(emoji, 'shortcuts', 0)

                if name:
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

    @ staticmethod
    def _parse_item(item, info=None):
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
                info.update(YouTubeChatDownloader._parse_item(renderer))

        BaseChatDownloader._move_to_dict(info, 'author')

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
                info['time_text'] = seconds_to_time(int(time_in_seconds))

        elif time_text is not None:  # doesn't have time in seconds, but has time text
            info['time_in_seconds'] = time_to_seconds(time_text)
        else:
            pass
            # has no current video time information
            # (usually live video or a sub-item)

        if 'message' not in info:  # Ensure the parsed item contains the 'message' key
            info['message'] = None

        return info

    @ staticmethod
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

    @ staticmethod
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

    @ staticmethod
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

        '₩': 'KRW',
        '￦': 'KRW',

        '¥': 'JPY',
        '￥': 'JPY',
    }

    # All other currency symbols use the ISO 4217 format:
    # https://en.wikipedia.org/wiki/ISO_4217
    # e.g. 'CHF', 'COP', 'HUF', 'PHP', 'PLN', 'RUB', 'SEK', 'PEN', 'ARS', 'CLP', 'NOK', 'BAM', 'SGD'

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
        'customThumbnail': r('badge_icons', _parse_thumbnails),

        # membership_item
        'headerPrimaryText': r('header_primary_text', _parse_header_text),
        'headerSubtext': r('header_secondary_text', _parse_header_text),
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
        'markChatItemsByAuthorAsDeletedAction': [  # TODO ban?
            'banUser'  # deletedStateMessage
        ],
        'markChatItemAsDeletedAction': [
            'deletedMessage'  # deletedStateMessage
        ]
    }

    _KNOWN_ADD_BANNER_TYPES = {
        'addBannerToLiveChatCommand': [
            'liveChatBannerRenderer',
            'liveChatBannerHeaderRenderer'
            'liveChatTextMessageRenderer'
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
    # removeChatItemAction
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
        'closeLiveChatActionPanelAction': []

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
        # print('b')

        # downloader.get_playlist_items

    _LIVE_PLAYLIST_URL = _YT_HOME + '/channel/UC4R8DWoMoI7CAwX8_LjQHig'

    def _get_testing_items(self):

        html, yt_info = self._get_initial_info(self._LIVE_PLAYLIST_URL)

        sections = yt_info['contents']['twoColumnBrowseResultsRenderer']['tabs'][
            0]['tabRenderer']['content']['sectionListRenderer']['contents']

        for section in sections:
            section_info = section['itemSectionRenderer']['contents'][0]['shelfRenderer']

            # print(section_info)

            # section_title = section_info['title']['runs'][0]['text']
            # print(section_title)

            # items = section_info['content']['horizontalListRenderer']['items']

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
        'viewCountText': r('view_count', lambda x: YouTubeChatDownloader._parse_runs(x)['message']),
        'shortViewCountText': r('short_view_count', lambda x: YouTubeChatDownloader._parse_runs(x)['message']),

        # 'videoId', 'thumbnail', 'title', 'viewCountText', 'navigationEndpoint', 'ownerBadges', 'trackingParams', 'shortViewCountText', 'menu', 'thumbnailOverlays'
    }

    @staticmethod
    def _parse_video(video_renderer):
        return r.remap_dict(video_renderer, YouTubeChatDownloader._VIDEO_REMAPPING)

    _VIDEO_TYPE_REMAPPING = {
        'live': (501, 'Live now'),
        'upcoming': (502, 'Upcoming live streams'),
        'past': (503, 'Past live streams')
    }

    def get_user_videos(self, channel_id=None, user_id=None, custom_username=None, video_type='live'):
        """[summary]
        If more than one of `channel_id`, `user_id` and `custom_username`
        are specifed, the first one specified will be returned.

        :param channel_id: [description], defaults to None
        :type channel_id: [type], optional
        :param user_id: [description], defaults to None
        :type user_id: [type], optional
        :param custom_username: [description], defaults to None
        :type custom_username: [type], optional
        :raises ValueError: [description]
        """

        _id = ''
        _type = ''
        if channel_id:
            _id = channel_id
            _type = 'channel'
        elif user_id:
            _id = user_id
            _type = 'user'
        elif custom_username:
            _id = custom_username
            _type = 'c'
        else:
            raise ValueError('No user type specified.')

        # live, past, upcoming
        vid_type = self._VIDEO_TYPE_REMAPPING.get(video_type.lower())

        if not vid_type:
            raise ValueError('Invalid argument passed for video_type. Must be one of {}'.format(
                set(self._VIDEO_TYPE_REMAPPING.keys())))

        user_url = 'https://www.youtube.com/{}/{}'.format(_type, _id)

        html, yt_info = self._get_initial_info(
            '{}/videos?view=2&live_view={}'.format(user_url, vid_type[0]))

        section_list_renderer = multi_get(
            yt_info, 'contents', 'twoColumnBrowseResultsRenderer', 'tabs', 1, 'tabRenderer', 'content', 'sectionListRenderer')

        if not section_list_renderer:
            raise UserNotFound('Unable to find user: "{}"'.format(user_url))

        # Check that the returned grid is what was asked for
        # YouTube tries to correct your mistake by selecting the uploads tab
        # if you try to access a tab that is not visible.
        sub_menu_items = multi_get(
            section_list_renderer, 'subMenu', 'channelSubMenuRenderer', 'contentTypeSubMenuItems')
        if not sub_menu_items:
            raise NoVideos('This channel has no videos.')

        selected = list(filter(lambda x: x['selected'], sub_menu_items))
        if not selected or selected[0]['title'] != vid_type[1]:
            log('debug', '"{}" tab is not visible for this channel (i.e. there are no such videos).'.format(
                vid_type[1]))
            return

        items = section_list_renderer['contents'][0]['itemSectionRenderer']['contents'][0]['gridRenderer']['items']

        for item in items:
            vid = item.get('gridVideoRenderer')
            if vid:
                yield self._parse_video(vid)
            else:
                print(item)

    def get_playlist_items(self, playlist_url):

        html, yt_info = self._get_initial_info(playlist_url)

        items = self._get_rendered_content(
            yt_info)['playlistVideoListRenderer']['contents']

        for item in items:
            playlist_video = item.get('playlistVideoRenderer')

            if playlist_video:
                yield self._parse_video(playlist_video)

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
            consent_id_match = re.search(self._CONSENT_ID_REGEX, consent)

            if consent_id_match:
                consent_id = consent_id_match.group()

        if not consent_id:
            consent_id = random.randint(100, 999)

        self.set_cookie_value('.youtube.com', 'CONSENT',
                              'YES+cb.20210328-17-p0.en+FX+{}'.format(consent_id))

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

    def _get_initial_info(self, url):
        html = self._session_get(url).text
        yt = re.search(self._YT_INITIAL_DATA_RE, html)
        yt_initial_data = try_parse_json(yt.group(1)) if yt else None
        return html, yt_initial_data

    def _get_initial_video_info(self, video_id):
        """ Get initial YouTube video information. """
        original_url = self._YT_VIDEO_TEMPLATE.format(video_id)

        html, yt_initial_data = self._get_initial_info(original_url)

        if not yt_initial_data:  # Fatal error
            raise ParsingError(
                'Unable to parse initial video data. {}'.format(html))

        details = {}

        cfg = re.search(self._YT_CFG_RE, html)
        details['ytcfg'] = try_parse_json(cfg.group(1)) if cfg else {}

        player_response = re.search(self._YT_INITIAL_PLAYER_RESPONSE_RE, html)
        player_response_info = try_parse_json(
            player_response.group(1)) if player_response else None

        if not player_response_info:
            log('warning', 'Unable to parse player response, proceeding with caution: {}'.format(html))
            player_response_info = {}

        streaming_data = player_response_info.get('streamingData') or {}
        formats = streaming_data.get(
            'adaptiveFormats') or streaming_data.get('formats')

        details['start_time'] = float_or_none(
            multi_get(formats, 0, 'lastModified'))

        # Try to get continuation info
        contents = yt_initial_data.get('contents') or {}

        conversation_bar = multi_get(
            contents, 'twoColumnWatchNextResults', 'conversationBar')
        sub_menu_items = multi_get(conversation_bar, 'liveChatRenderer', 'header', 'liveChatHeaderRenderer',
                                   'viewSelector', 'sortFilterSubMenuRenderer', 'subMenuItems') or {}
        details['continuation_info'] = {
            x['title']: x['continuation']['reloadContinuationData']['continuation']
            for x in sub_menu_items
        }
        details['is_live'] = 'Live chat' in details['continuation_info']

        playability_status = player_response_info.get(
            'playabilityStatus') or {}
        status = playability_status.get('status')
        error_screen = playability_status.get('errorScreen')

        # Only raise an error if there is no continuation info. Sometimes you
        # are able to view chat, but not the video (e.g. for very long livestreams)
        if not details['continuation_info']:
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
                            error_message += ' {}.'.format(
                                error_reasons[error_reason].rstrip('.'))
                        else:
                            error_message += str(error_reasons[error_reason])

                error_message = error_message.strip()

                if status == 'ERROR':
                    raise VideoUnavailable(error_message)
                elif status == 'LOGIN_REQUIRED':
                    raise LoginRequired(error_message)
                elif status == 'UNPLAYABLE':
                    raise VideoUnplayable(error_message)
                else:
                    log('debug', 'Unknown status: {}. {}'.format(
                        status, playability_status))
                    error_message = '{}: {}'.format(status, error_message)
                    raise VideoUnavailable(error_message)
            elif not contents:
                log('debug', 'Initial YouTube data: {}'.format(yt_initial_data))
                raise VideoUnavailable(
                    'Unable to find initial video contents.')
            else:
                # Video exists, but you cannot view chat for some reason

                error_runs = multi_get(conversation_bar, 'conversationBarRenderer',
                                       'availabilityMessage', 'messageRenderer', 'text')
                error_message = self._parse_runs(error_runs, False)[
                    'message'] if error_runs else 'Video does not have a chat replay.'

                raise NoChatReplay(error_message)

        video_details = player_response_info.get('videoDetails') or {}
        details['title'] = video_details.get('title')
        details['duration'] = int_or_none(video_details.get('lengthSeconds'))
        return details

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

        visitor_data = multi_get(
            ytcfg, 'INNERTUBE_CONTEXT', 'client', 'visitorData')
        if visitor_data:
            headers['x-goog-visitor-id'] = visitor_data

        auth = self._generate_sapisidhash_header()
        if auth:
            headers['authorization'] = auth

        return headers

    def _get_chat_messages(self, initial_info, params):

        initial_continuation_info = initial_info.get('continuation_info') or {}

        # stream_start_time = initial_info.get('start_time')
        is_live = initial_info.get('is_live')

        # duration = initial_info.get('duration')

        start_time = ensure_seconds(params.get('start_time'))
        end_time = ensure_seconds(params.get('end_time'))

        # Top chat replay - Some messages, such as potential spam, may not be visible
        # Live chat replay - All messages are visible
        chat_type = params.get('chat_type').title()  # Live or Top

        continuation_items = list(initial_continuation_info.items())
        if len(continuation_items) < 2:
            raise NoContinuation(
                'Initial continuation information could not be found: {}'.format(initial_continuation_info))

        continuation_index = 0 if chat_type == 'Top' else 1
        continuation = continuation_items[continuation_index][1]
        log('debug', 'Getting {} chat ({}).'.format(
            chat_type, continuation_items[continuation_index][0]))

        api_type = 'live_chat'
        if not is_live:
            api_type += '_replay'

        init_page = self._YOUTUBE_INIT_API_TEMPLATE.format(
            api_type, continuation)

        ytcfg = initial_info.get('ytcfg')

        api_key = ytcfg.get('INNERTUBE_API_KEY')

        continuation_url = self._YOUTUBE_CHAT_API_TEMPLATE.format(
            api_type, api_key)
        offset_milliseconds = (
            start_time * 1000) if isinstance(start_time, (float, int)) else None

        # force_no_timeout = params.get('force_no_timeout')

        max_attempts = params.get('max_attempts')
        retry_timeout = params.get('retry_timeout')

        messages_groups_to_add = params.get('message_groups') or []
        messages_types_to_add = params.get('message_types') or []

        invalid_groups = set(messages_groups_to_add) - \
            self._MESSAGE_GROUPS.keys()
        if 'all' not in messages_groups_to_add and invalid_groups:
            raise InvalidParameter(
                'Invalid groups specified: {}'.format(invalid_groups))

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

            info = None
            for attempt_number in attempts(max_attempts):

                try:
                    if first_time:
                        # must run to get first few messages, otherwise might miss some
                        html, yt_info = self._get_initial_info(init_page)

                    else:
                        if not is_live and offset_milliseconds is not None:
                            continuation_params['currentPlayerState'] = {
                                'playerOffsetMs': offset_milliseconds}

                        if click_tracking_params:
                            continuation_params['context']['clickTracking'] = {
                                'clickTrackingParams': click_tracking_params}

                        yt_info = self._session_post(
                            continuation_url, json=continuation_params).json()

                    debug_info = {
                        'click_tracking': multi_get(continuation_params, 'context', 'clickTracking'),
                        'continuation': multi_get(continuation_params, 'continuation')
                    }
                    log('debug', 'Continuation parameters: {}'.format(debug_info))
                    log('debug', 'Session headers: {}'.format(
                        ', '.join(self.session.headers.keys())))  # Only display keys

                    info = multi_get(
                        yt_info, 'continuationContents', 'liveChatContinuation')

                    logged_in_info = multi_get(
                        yt_info, 'responseContext', 'serviceTrackingParams', 1, 'params', 0)
                    log('debug', 'Logged-in info: {}'.format(logged_in_info))

                    if not info:
                        log('debug', 'No continuation information found: {}'.format(
                            yt_info))

                        # Check for errors:
                        error = yt_info.get('error')
                        if error:
                            error_code = error.get('code')
                            error_message = error.get('message')

                            if error_code // 100 == 5:  # Server error, retry
                                self.retry(
                                    attempt_number, max_attempts, retry_timeout=retry_timeout, text=error_message)
                                continue

                        return

                    break  # successful retrieve

                except (JSONDecodeError, RequestException) as e:
                    self.retry(attempt_number, max_attempts, e, retry_timeout)
                    continue

            actions = info.get('actions') or []

            if actions:
                for action in actions:
                    # print(action)
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
                        data = self._parse_item(original_item, data)

                    elif original_action_type in self._KNOWN_REMOVE_ACTION_TYPES:
                        original_item = action
                        if original_action_type == 'markChatItemAsDeletedAction':
                            original_message_type = 'deletedMessage'
                        else:  # markChatItemsByAuthorAsDeletedAction
                            original_message_type = 'banUser'

                        data = self._parse_item(original_item, data)

                    elif original_action_type in self._KNOWN_REPLACE_ACTION_TYPES:
                        original_item = multi_get(
                            action, original_action_type, 'replacementItem')

                        original_message_type = try_get_first_key(
                            original_item)
                        data = self._parse_item(original_item, data)

                    elif original_action_type in self._KNOWN_TOOLTIP_ACTION_TYPES:
                        original_item = multi_get(
                            action, original_action_type, 'tooltip')

                        original_message_type = try_get_first_key(
                            original_item)
                        data = self._parse_item(original_item, data)

                    elif original_action_type in self._KNOWN_ADD_BANNER_TYPES:
                        original_item = multi_get(
                            action, original_action_type, 'bannerRenderer')

                        if original_item:
                            original_message_type = try_get_first_key(
                                original_item)

                            header = original_item[original_message_type].get(
                                'header')
                            parsed_header = self._parse_item(header)
                            header_message = parsed_header.get('message')

                            contents = original_item[original_message_type].get(
                                'contents')
                            parsed_contents = self._parse_item(contents)

                            data.update(parsed_header)
                            data.update(parsed_contents)
                            data['header_message'] = header_message
                        else:
                            self._debug_log(params,
                                            'No bannerRenderer item',
                                            'Action type: {}'.format(
                                                original_action_type),
                                            'Action: {}'.format(action),
                                            'Parsed data: {}'.format(data)
                                            )

                    elif original_action_type in self._KNOWN_REMOVE_BANNER_TYPES:
                        original_item = action
                        original_message_type = 'removeBanner'
                        data = self._parse_item(original_item, data)

                    elif original_action_type in self._KNOWN_IGNORE_ACTION_TYPES:
                        continue
                        # ignore these
                    else:
                        # not processing these
                        self._debug_log(params,
                                        'Unknown action: {}'.format(
                                            original_action_type),
                                        action,
                                        data
                                        )

                    test_for_missing_keys = original_item.get(
                        original_message_type, {}).keys()
                    missing_keys = test_for_missing_keys - self._KNOWN_KEYS

                    # print(action)
                    if not data:  # TODO debug
                        self._debug_log(params,
                                        'Parse of action returned empty results: {}'.format(
                                            original_action_type),
                                        action
                                        )

                    if missing_keys:  # TODO debugging for missing keys
                        self._debug_log(params,
                                        'Missing keys found: {}'.format(
                                            missing_keys),
                                        'Message type: {}'.format(
                                            original_message_type),
                                        'Action type: {}'.format(
                                            original_action_type),
                                        'Action: {}'.format(action),
                                        'Parsed data: {}'.format(data)
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
                            self._debug_log(params,
                                            'Unknown message type "{}" for action "{}"'.format(
                                                original_message_type,
                                                original_action_type
                                            ),
                                            'New message type: {}'.format(
                                                data['message_type']),
                                            'Action: {}'.format(action),
                                            'Parsed data: {}'.format(data)
                                            )

                    else:  # no type # can ignore message
                        self._debug_log(params,
                                        'No message type',
                                        'Action type: {}'.format(
                                            original_action_type),
                                        'Action: {}'.format(action),
                                        'Parsed data: {}'.format(data)
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
                    if not is_live:
                        # assume message is at beginning if it does not have a time component
                        time_in_seconds = data.get('time_in_seconds', 0)

                        before_start = start_time is not None and time_in_seconds < start_time
                        after_end = end_time is not None and time_in_seconds > end_time

                        if first_time and before_start:
                            continue  # first time and invalid start time
                        elif before_start or after_end:
                            return  # while actually searching, if time is invalid

                    # try to reconstruct time in seconds from timestamp and stream start
                    # if data.get('time_in_seconds') is None and data.get('timestamp') is not None:
                    #     data['time_in_seconds'] = (data['timestamp'] - stream_start_time)/1e6
                    #     data['time_text'] = seconds_to_time(int(data['time_in_seconds']))

                    #     pass
                    # valid timing, add

                    message_count += 1
                    yield data

                log('debug', 'Total number of messages: {}'.format(message_count))

            elif not is_live:
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

                log('debug', 'Continuation info: {}'.format(continuation_info))

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
                    self._debug_log(params,
                                    'Unknown continuation: {}'.format(
                                        continuation_key),
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

                    log('debug', 'Sleeping for {}ms.'.format(sleep_duration))
                    interruptible_sleep(sleep_duration / 1000)

            if no_continuation:  # no continuation, end
                break

            if first_time:
                first_time = False

    # def get_chat_by_user(self, channel_id=None, user_id=None, custom_username=None):
    #     def get_user_videos(self, video_type='live'):

    def _get_chat_by_user(self, match, params):
        match_id = match.group('id')
        user_type = match.group('type')  # channel|c|user

        if user_type == 'channel':
            return self.get_chat_by_channel_id(match_id, params)

        if user_type == 'user':
            return self.get_chat_by_user_id(match_id, params)

        # Otherwise assume custom username
        return self.get_chat_by_custom_username(match_id, params)

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

    def _get_chat_by_user_args(self, user_video_args, params):
        # TODO add param for wait time
        # params['exit_on_fail'] = True

        title = try_get_first_value(user_video_args)

        chat_item = Chat(title=title)  # Create empty chat object
        chat_item.chat = self._get_chat_messages_by_user_args(
            user_video_args, chat_item, params)

        return chat_item

    def _get_chat_messages_by_user_args(self, user_video_args, chat_item, params):
        # chat_item allows to change title and info based on new info

        list_of_vids_to_ignore = params.get('ignore') or []

        sleep_amount = 30  # params.get('retry_timeout')

        while True:
            for video_type in ('live', 'upcoming'):
                # prioritise live videos
                for video in self.get_user_videos(**user_video_args, video_type=video_type):
                    video_id = video['video_id']
                    video_title = video['title']

                    if video_id in list_of_vids_to_ignore:
                        log('debug', 'Skipping video with ID: "{}"'.format(video_id))
                        continue

                    try:
                        chat = self.get_chat_by_video_id(video_id, params)

                        log('info', 'Found a{} livestream: "{}" ({}).'.format(
                            'n upcoming' if video_type == 'upcoming' else '', video_title, video_id))

                        # update chat item by copying over
                        chat_dict = chat.__dict__.copy()
                        for key in ('chat', 'callback'):
                            chat_dict.pop(key, None)

                        for i in chat_dict:
                            setattr(chat_item, i, chat_dict[i])

                        yield from chat.chat
                        break

                    except ChatDownloaderError as e:
                        # For some reason, doesn't work
                        log('warning', 'Unable to get chat for "{}" ({}) due to an error: "{}"'.format(
                            video['title'], video_id, e))
                        # TODO exit on error?

            log('info', 'There are no active or upcoming livestreams with a live chat. Retrying in {} seconds.'.format(
                sleep_amount))
            interruptible_sleep(sleep_amount)

            # continue forever, until reaching a video with valid chat

    def get_chat_by_video_id(self, video_id, params):
        """Get chat messages for a YouTube video, given its ID.

        :param video_id: YouTube video ID
        :type video_id: str
        :return: Chat object for the corresponding YouTube video
        :rtype: Chat
        """
        initial_info = self._get_initial_video_info(video_id)

        title = initial_info.get('title')
        duration = initial_info.get('duration')
        start_time = initial_info.get('start_time')
        is_live = initial_info.get('is_live')

        return Chat(
            self._get_chat_messages(initial_info, params),
            title=title,
            duration=duration,
            is_live=is_live,
            start_time=start_time
        )

    def _get_chat_by_video_id(self, match, params):
        return self.get_chat_by_video_id(match.group('id'), params)
