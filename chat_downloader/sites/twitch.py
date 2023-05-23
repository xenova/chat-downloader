from .common import (
    Chat,
    BaseChatDownloader,
    Remapper as r,
    Image
)

from ..errors import (
    SiteError,
    NoChatReplay,
    VideoUnavailable,
    UserNotFound
)

from ..utils.core import (
    ensure_seconds,
    timestamp_to_microseconds,
    seconds_to_time,
    int_or_none,
    str_or_none,
    replace_with_underscores,
    multi_get,
    remove_prefixes,
    attempts
)

from ..debugging import (
    log,
    debug_log
)

import re
import json
import time
import socket
import base64
import math
from requests.exceptions import RequestException
from json.decoder import JSONDecodeError


class TwitchError(SiteError):
    """Raised when an error occurs with a Twitch video."""
    pass


# TODO export as another module?


class TwitchChatIRC():

    def __init__(self):
        # create new socket
        self.socket = socket.socket()

        # start connection
        self.socket.connect(('irc.chat.twitch.tv', 6667))
        # print('Connected to', self._HOST, 'on port', self._PORT)

        self.current_channel = None
        # https://dev.twitch.tv/docs/irc/tags
        # https://dev.twitch.tv/docs/irc/membership
        # https://dev.twitch.tv/docs/irc/commands

        # twitch.tv/membership
        self.send_raw(
            'CAP REQ :twitch.tv/tags twitch.tv/commands twitch.tv/membership')
        self.send_raw('PASS SCHMOOPIIE')
        self.send_raw('NICK justinfan67420')

    def send_raw(self, string):
        self.socket.send((string + '\r\n').encode('utf-8'))

    def recv(self, buffer_size):
        return self.socket.recv(buffer_size).decode('utf-8', 'ignore')

    def join_channel(self, channel_name):
        channel_lower = channel_name.lower()

        if self.current_channel != channel_lower:
            self.send_raw(f'JOIN #{channel_lower}')
            self.current_channel = channel_lower

    def set_timeout(self, message_receive_timeout):
        self.socket.settimeout(message_receive_timeout)

    def close_connection(self):
        self.socket.close()


class TwitchChatDownloader(BaseChatDownloader):
    _BADGE_INFO = {}
    _SUBSCRIBER_BADGE_INFO = {}  # local cache for subscriber badge info

    _NAME = 'twitch.tv'

    _TESTS = [
        # Live
        {
            'name': 'Livestream',
            'params': {
                'url': 'https://www.twitch.tv/xenova',
                'timeout': 5
            }
        },

        # Past broadcasts
        {
            'name': 'Past broadcast with chat replay.',
            'params': {
                'url': 'https://www.twitch.tv/videos/87136772',
                'max_messages': 30
            },
            'expected_result': {
                'message_types': ['text_message'],
                # 'action_types': [],
                'messages_condition': lambda messages: len(messages) <= 30
            }
        },

        # Clip
        {
            'name': 'Clip with chat replay.',
            'params': {
                'url': 'https://clips.twitch.tv/TrappedFrigidPenguinSeemsGood',
            },
            'expected_result': {
                'message_types': ['text_message'],
                # 'action_types': [],
                'messages_condition': lambda messages: len(messages) > 0
                # 'error': LoginRequired,
            }
        },


        # Commenter is "None"
        # https://www.twitch.tv/videos/873616984 --start_time 1:26:10


        {
            'name': "This clip's past broadcast has expired and chat replay is no longer available.",
            'params': {
                'url': 'https://clips.twitch.tv/AverageSparklyTortoisePeoplesChamp',
            },
            'expected_result': {
                'error': NoChatReplay
            }
        },
        {
            'name': "Sorry. Unless you've got a time machine, that content is unavailable.",
            'params': {
                'url': 'https://www.twitch.tv/videos/1',
            },
            'expected_result': {
                'error': VideoUnavailable
            }
        },
    ]

    # clips
    # vod
    # name -> live

    _SITE_DEFAULT_PARAMS = {
        'format': 'twitch',
    }

    _VALID_URLS = {
        # e.g. 'http://www.twitch.tv/riotgames/v/6528877?t=5m10s'
        '_get_chat_by_vod_id': r'''(?x)
                    https?://
                        (?:
                            (?:(?:www|go|m)\.)?twitch\.tv/(?:[^/]+/v(?:ideo)?|videos)/|
                            player\.twitch\.tv/\?.*?\bvideo=v?
                        )
                        (?P<id>\d+)
                    ''',

        # e.g. 'https://clips.twitch.tv/FaintLightGullWholeWheat'
        '_get_chat_by_clip_id': r'''(?x)
                        https?://
                            (?:
                                clips\.twitch\.tv/(?:embed\?.*?\bclip=|(?:[^/]+/)*)|
                                (?:(?:www|go|m)\.)?twitch\.tv/[^/]+/clip/
                            )
                            (?P<id>[^/?#&]+)
                        ''',

        # e.g. 'http://www.twitch.tv/shroomztv'
        '_get_chat_by_stream_id': r'''(?x)
                        https?://
                            (?:
                                (?:(?:www|go|m)\.)?twitch\.tv/|
                                player\.twitch\.tv/\?.*?\bchannel=
                            )
                            (?P<id>[^/#?]+)
                        '''
    }

    # _CLIENT_ID = 'kimne78kx3ncx6brgo4mv6wki5h1ko'  # public client id
    _CLIENT_ID = 'kd1unb4b3q4t58fwlpcbzcbnm76a8fp'  # public client id

    _GQL_API_URL = 'https://gql.twitch.tv/gql'

    _PING_TEXT = 'PING :tmi.twitch.tv'
    _PONG_TEXT = 'PONG :tmi.twitch.tv'

    _SUBSCRIPTION_TYPES = {
        'Prime': 'Prime',
        '1000': 'Tier 1',
        '2000': 'Tier 2',
        '3000': 'Tier 3'
    }

    @staticmethod
    def _parse_bool(text):
        return text == '1'

    @staticmethod
    def _parse_bool_text(text):
        return text == 'true'

    @staticmethod
    def _parse_author_images(original_url):
        # e.g. https://static-cdn.jtvnw.net/jtv_user_pictures/3892c956-0616-4fc9-b2fe-527b1be0b623-profile_image-300x300.png
        smaller_icon = original_url.replace('300x300', '70x70')
        return [
            Image(original_url, 300, 300).json(),
            Image(smaller_icon, 70, 70).json(),
        ]

    @staticmethod
    def _parse_message_info(message):
        message_info = {
            'author_colour': message.get('userColor'),
            'author_badges': message.get('userBadges') or [],
        }

        message_text = ''
        emotes = {}
        emote_locations = {}

        for fragment in message['fragments']:
            message_text += fragment['text']

            emote = fragment.get('emote')
            if emote:
                emote_id = emote['emoteID']
                _, *positions = emote['id'].split(';')

                begin, end = map(int, positions)

                if emote_id not in emotes:
                    emote_locations[emote_id] = []
                    emotes[emote_id] = {
                        'id': emote_id,
                        'images': TwitchChatDownloader._generate_emote_image_list(emote_id),
                        'name': message_text[begin:end + 1]
                    }

                emote_locations[emote_id].append(f'{begin}-{end}')

        message_info['message'] = message_text

        if emotes:
            for emote_id in emotes:
                emotes[emote_id]['locations'] = ','.join(
                    emote_locations[emote_id])
            message_info['emotes'] = list(emotes.values())

        return message_info

    @staticmethod
    def _decode_pseudo_BNF(text):
        """
        Decode text according to https://ircv3.net/specs/extensions/message-tags.html
        """
        return text.replace(r'\:', ';').replace(r'\s', ' ')

    @staticmethod
    def _generate_emote_image_list(emote_id):
        emote_image_list = []
        for theme in ('light', 'dark'):
            for size in ((28, '1.0'), (56, '2.0'), (112, '3.0')):
                image = Image(
                    TwitchChatDownloader._EMOTE_URL_TEMPLATE.format(
                        emote_id, theme, size[1]),
                    size[0],
                    size[0],
                    f'{size[0]}x{size[0]}-{theme}'
                ).json()

                emote_image_list.append(image)
        return emote_image_list

    _EMOTE_REGEX = r'(\w+):([\d,-]+)'
    _EMOTE_URL_TEMPLATE = 'https://static-cdn.jtvnw.net/emoticons/v2/{}/default/{}/{}'

    @staticmethod
    def _parse_emotes(text):
        # Information to replace text in the message with emote images. This can be empty.
        # <emote ID>:<first index>-<last index>,<another first index>-<another last index>/<another emote ID>:<first index>-<last index>
        emotes = []

        matches = re.findall(TwitchChatDownloader._EMOTE_REGEX, text)

        for match in matches:
            emote_id = match[0]
            emote = {
                'id': emote_id,
                'locations': match[1].split(','),
                'images': TwitchChatDownloader._generate_emote_image_list(emote_id)
            }
            emotes.append(emote)

        return emotes

    _AUTHOR_REMAPPING = {
        '_id': r('id', str_or_none),
        'name': 'name',
        'display_name': 'display_name',
        'logo': r('images', _parse_author_images),
        'type': 'type',
        'created_at': r('created_at', timestamp_to_microseconds),
        # 'updated_at': r('updated_at', 'parse_timestamp'),
        'bio': 'bio'
    }

    _USER_REMAPPING = {
        'id': 'id',
        'login': 'name',
        'displayName': 'display_name',
        'profileImageURL': 'profile_image_url',
        'primaryColorHex': 'colour'
    }

    @staticmethod
    def _parse_user(item):
        if isinstance(item, dict):
            return r.remap_dict(item, TwitchChatDownloader._USER_REMAPPING)
        return {}

    _COMMENT_REMAPPING = {
        'id': 'message_id',
        'createdAt': r('timestamp', timestamp_to_microseconds),
        'commenter': r('author', _parse_user),

        'contentOffsetSeconds': 'time_in_seconds',

        # TODO make sure body vs. fragments okay
        'message': r(None, _parse_message_info, True)
    }

    _MESSAGE_PARAM_REMAPPING = {
        'msg-id': 'message_type',

        'msg-param-cumulative-months': r('cumulative_months', int_or_none),
        'msg-param-months': r('months', int_or_none),
        'msg-param-displayName': 'raider_display_name',
        'msg-param-login': 'raider_name',
        'msg-param-viewerCount': r('number_of_raiders', int_or_none),

        'msg-param-promo-name': 'promotion_name',
        'msg-param-promo-gift-total': 'number_of_gifts_given_during_promo',

        'msg-param-recipient-id': 'gift_recipient_id',
        'msg-param-recipient-user-name': 'gift_recipient_display_name',
        'msg-param-recipient-display-name': 'gift_recipient_display_name',
        'msg-param-gift-months': r('number_of_months_gifted', int_or_none),


        'msg-param-sender-login': 'gifter_name',
        'msg-param-sender-name': 'gifter_display_name',

        'msg-param-should-share-streak': r('user_wants_to_share_streaks', _parse_bool),
        'msg-param-streak-months': r('number_of_consecutive_months_subscribed', int_or_none),
        'msg-param-sub-plan': r('subscription_type', lambda x: TwitchChatDownloader._SUBSCRIPTION_TYPES.get(x)),
        'msg-param-sub-plan-name': r('subscription_plan_name', _decode_pseudo_BNF),
        'msg-param-sub-benefit-end-month': r('sub_benefit_end_month', int_or_none),

        'msg-param-ritual-name': 'ritual_name',

        'msg-param-threshold': 'bits_badge_tier',


        # found in vods

        # resub
        'msg-param-multimonth-duration': r('multimonth_duration', int_or_none),
        'msg-param-multimonth-tenure': r('multimonth_tenure', int_or_none),
        'msg-param-was-gifted': r('was_gifted', _parse_bool_text),

        'msg-param-gifter-id': 'gifter_id',
        'msg-param-gifter-login': 'gifter_name',
        'msg-param-gifter-name': 'gifter_display_name',
        'msg-param-anon-gift': r('was_anonymous_gift', _parse_bool_text),
        'msg-param-gift-month-being-redeemed': r('gift_months_being_redeemed', int_or_none),

        # rewardgift
        'msg-param-domain': 'domain',
        'msg-param-selected-count': r('selected_count', int_or_none),
        'msg-param-trigger-type': 'trigger_type',
        'msg-param-total-reward-count': r('total_reward_count', int_or_none),
        'msg-param-trigger-amount': r('trigger_amount', int_or_none),

        # submysterygift
        'msg-param-origin-id': r('origin_id', _decode_pseudo_BNF),
        'msg-param-sender-count': r('sender_count', int_or_none),
        'msg-param-mass-gift-count': r('mass_gift_count', int_or_none),

        # communitypayforward
        'msg-param-prior-gifter-anonymous': r('prior_gifter_anonymous', _parse_bool_text),
        'msg-param-prior-gifter-user-name': 'prior_gifter_name',
        'msg-param-prior-gifter-display-name': 'prior_gifter_display_name',
        'msg-param-prior-gifter-id': 'prior_gifter_id',

        'msg-param-fun-string': 'fun_string',

        # charity
        'msg-param-charity': 'charity',
        'msg-param-charity-name': 'charity_name',
        'msg-param-charity-hashtag': 'charity_hashtag',
        'msg-param-charity-learn-more': 'charity_link',
        'msg-param-charity-hours-remaining': r('charity_hours_remaining', int_or_none),
        'msg-param-charity-days-remaining': r('charity_days_remaining', int_or_none),
        'msg-param-total': r('charity_total_raised', int_or_none),

        # not come across yet, but other tools have it:
        # 'msg-param-bits-amount':'bits_amount',
        # 'msg-param-streak-tenure-months':'streak_tenureBaseChatDownloaderBase#
        # 'msg-param-userID':'user_id',
        #
        # 'msg-param-cumulative-tenure-months':'cumulative_tenure_months',
        # 'msg-param-should-share-streak-tenure':'should-share-streak-tenure',
        # 'msg-param-min-cheer-amount' :'minimum_cheer_amount',
        # 'msg-param-gift-name':'gift_name',




        # to remove later
        'msg-param-profileImageURL': 'profile_image_url'
    }

    # Create set of known types
    _KNOWN_COMMENT_KEYS = {
        # created elsewhere
        'message', 'time_in_seconds', 'message_id', 'time_text', 'author', 'timestamp', 'message_type', 'emotes'
    }

    _KNOWN_COMMENT_KEYS.update(BaseChatDownloader.get_mapped_keys({
        **_COMMENT_REMAPPING, **_MESSAGE_PARAM_REMAPPING
    }))

    _IRC_REMAPPING = {
        # CLEARCHAT
        # Purges all chat messages in a channel, or purges chat messages from a specific user, typically after a timeout or ban.
        # (Optional) Duration of the timeout, in seconds. If omitted, the ban is permanent.
        'ban-duration': r('ban_duration', int_or_none),

        # CLEARMSG
        # Removes a single message from a channel. This is triggered by the/delete <target-msg-id> command on IRC.
        # Name of the user who sent the message.
        'login': 'author_name',
        # UUID of the message.
        'target-msg-id': 'target_message_id',


        # GLOBALUSERSTATE
        # On successful login, provides data about the current logged-in user through IRC tags. It is sent after successfully authenticating (sending a PASS/NICK command).

        'emote-sets': 'emote_sets',  # TODO split by,?

        # GENERAL
        # can be empty (which means it depends on dark/light theme)
        'color': 'colour',
        'display-name': 'author_display_name',
        'user-id': r('author_id', str_or_none),



        # reply-parent-display-name


        # PRIVMSG
        'badge-info': 'author_badge_metadata',
        'badges': 'author_badges',

        'bits': r('bits', int_or_none),

        'id': 'message_id',
        'mod': r('author_is_moderator', _parse_bool),
        'room-id': r('channel_id', str_or_none),
        'tmi-sent-ts': r('timestamp', lambda x: int_or_none(x, 0) * 1000),

        'subscriber': r('author_is_subscriber', _parse_bool),
        'turbo': r('author_is_turbo', _parse_bool),

        'client-nonce': 'client_nonce',

        'user-type': 'user_type',



        'reply-parent-msg-body': r('in_reply_to_message', _decode_pseudo_BNF),
        'reply-parent-user-id': r('in_reply_to_author_id', str_or_none),

        'reply-parent-msg-id': 'in_reply_to_message_id',
        'reply-parent-display-name': 'in_reply_to_author_display_name',
        'reply-parent-user-login': 'in_reply_to_author_name',

        'crowd-chant-parent-msg-id': 'crowd_chant_in_reply_to_message_id',

        'custom-reward-id': 'custom_reward_id',


        'emotes': r('emotes', _parse_emotes),
        'flags': 'flags',
        'first-msg': r('is_first_message', _parse_bool),
        'returning-chatter': r('is_returning_chatter', _parse_bool),
        'vip': r('is_vip', _parse_bool),


        # ROOMSTATE
        'emote-only': r('emote_only', _parse_bool),
        'followers-only': r('follower_only', int_or_none),

        'r9k': r('r9k_mode', _parse_bool),
        'slow': r('slow_mode', int_or_none),
        'subs-only': r('subscriber_only', _parse_bool),
        'rituals': r('rituals_enabled', _parse_bool),

        # USERNOTICE
        'system-msg': r('system_message', _decode_pseudo_BNF),

        # (Commands)
        # HOSTTARGET
        'number-of-viewers': 'number_of_viewers',

        # ban user
        'target-user-id': r('target_author_id', str_or_none),

        # USERNOTICE - other
        **_MESSAGE_PARAM_REMAPPING
    }

    _KNOWN_IRC_KEYS = {
        # banned user
        'banned_user', 'ban_type',

        # slow mode
        'seconds_to_wait',

        # follower only
        'minutes_to_follow_before_chatting',

        # parsed elsewhere
        'action_type',
        'author',
        'in_reply_to',
        'message'
    }
    _KNOWN_IRC_KEYS.update(BaseChatDownloader.get_mapped_keys(_IRC_REMAPPING))

    _ACTION_TYPE_REMAPPING = {
        # tags
        'CLEARCHAT': 'clear_chat',
        'CLEARMSG': 'delete_message',
        'GLOBALUSERSTATE': 'successful_login',
        'PRIVMSG': 'text_message',
        'ROOMSTATE': 'room_state',
        'USERNOTICE': 'user_notice',
        'USERSTATE': 'user_state',

        # commands
        'HOSTTARGET': 'host_target',
        'NOTICE': 'notice',
        'RECONNECT': 'reconnect'
    }

    # MESSAGE GROUPS FOR IRC
    _MESSAGE_GROUP_REMAPPINGS = {
        # TODO add rest of
        # https://dev.twitch.tv/docs/irc/msg-id

        'messages': {
            'highlighted-message': 'highlighted_message',
            'skip-subs-mode-message': 'send_message_in_subscriber_only_mode',
        },
        'bits': {
            'bitsbadgetier': 'bits_badge_tier',
        },
        'subscriptions': {
            'sub': 'subscription',
            'resub': 'resubscription',
            'subgift': 'subscription_gift',
            'anonsubgift': 'anonymous_subscription_gift',
            'anonsubmysterygift': 'anonymous_mystery_subscription_gift',
            'submysterygift': 'mystery_subscription_gift',
            'extendsub': 'extend_subscription',

            'standardpayforward': 'standard_pay_forward',
            'communitypayforward': 'community_pay_forward',
            'primecommunitygiftreceived': 'prime_community_gift_received',
        },
        'upgrades': {
            'primepaidupgrade': 'prime_paid_upgrade',
            'giftpaidupgrade': 'gift_paid_upgrade',
            'rewardgift': 'reward_gift',
            'anongiftpaidupgrade': 'anonymous_gift_paid_upgrade',
        },
        'raids': {
            'raid': 'raid',
            'unraid': 'unraid'
        },
        'hosts': {
            'host_on': 'start_host',
            'host_off': 'end_host',
            'bad_host_hosting': 'bad_host_hosting',
            'bad_host_rate_exceeded': 'bad_host_rate_exceeded',
            'bad_host_error': 'bad_host_error',
            'hosts_remaining': 'hosts_remaining',
            'not_hosting': 'not_hosting',

            'host_target_went_offline': 'host_target_went_offline',
        },
        'rituals': {
            'ritual': 'ritual',
        },
        'room_states': {
            # slow mode
            'slow_on': 'enable_slow_mode',
            'slow_off': 'disable_slow_mode',
            'already_slow_on': 'slow_mode_already_on',
            'already_slow_off': 'slow_mode_already_off',

            # sub only mode
            'subs_on': 'enable_subscriber_only_mode',
            'subs_off': 'disable_subscriber_only_mode',
            'already_subs_on': 'sub_mode_already_on',
            'already_subs_off': 'sub_mode_already_off',

            # emote only mode
            'emote_only_on': 'enable_emote_only_mode',
            'emote_only_off': 'disable_emote_only_mode',
            'already_emote_only_on': 'emote_only_already_on',
            'already_emote_only_off': 'emote_only_already_off',

            # r9k mode
            'r9k_on': 'enable_r9k_mode',
            'r9k_off': 'disable_r9k_mode',
            'already_r9k_on': 'r9k_mode_already_on',
            'already_r9k_off': 'r9k_mode_already_off',

            # follower only mode
            'followers_on': 'enable_follower_only_mode',
            'followers_on_zero': 'enable_follower_only_mode',  # same thing, handled in parse
            'followers_off': 'disable_follower_only_mode',
            'already_followers_on': 'follower_only_mode_already_on',
            'already_followers_on_zero': 'follower_only_mode_already_on',
            'already_followers_off': 'follower_only_mode_already_off',

        },
        'deleted_messages': {
            'msg_banned': 'banned_message',

            'bad_delete_message_error': 'bad_delete_message_error',
            'bad_delete_message_broadcaster': 'bad_delete_message_broadcaster',
            'bad_delete_message_mod': 'bad_delete_message_mod',
            'delete_message_success': 'delete_message_success',
        },
        'bans': {

            # ban
            'already_banned': 'already_banned',
            'bad_ban_self': 'bad_ban_self',
            'bad_ban_broadcaster': 'bad_ban_broadcaster',
            'bad_ban_admin': 'bad_ban_admin',
            'bad_ban_global_mod': 'bad_ban_global_mod',
            'bad_ban_staff': 'bad_ban_staff',
            'ban_success': 'ban_success',

            # unban
            'bad_unban_no_ban': 'bad_unban_no_ban',
            'unban_success': 'unban_success',

            'msg_channel_suspended': 'channel_suspended_message',

            # timeouts
            'timeout_success': 'timeout_success',

            # timeout errors
            'bad_timeout_self': 'bad_timeout_self',
            'bad_timeout_broadcaster': 'bad_timeout_broadcaster',
            'bad_timeout_mod': 'bad_timeout_mod',
            'bad_timeout_admin': 'bad_timeout_admin',
            'bad_timeout_global_mod': 'bad_timeout_global_mod',
            'bad_timeout_staff': 'bad_timeout_staff',
        },
        'mods': {
            'bad_mod_banned': 'bad_mod_banned',
            'bad_mod_mod': 'bad_mod_mod',
            'mod_success': 'mod_success',
            'bad_unmod_mod': 'bad_unmod_mod',
            'unmod_success': 'unmod_success',
            'no_mods': 'no_mods',
            'room_mods': 'room_mods',
        },
        'colours': {
            'turbo_only_color': 'turbo_only_colour',
            'color_changed': 'colour_changed',
        },
        'commercials': {
            'bad_commercial_error': 'bad_commercial_error',
            'commercial_success': 'commercial_success',
        },

        'vips': {
            'bad_vip_grantee_banned': 'bad_vip_grantee_banned',
            'bad_vip_grantee_already_vip': 'bad_vip_grantee_already_vip',
            'vip_success': 'vip_success',
            'bad_unvip_grantee_not_vip': 'bad_unvip_grantee_not_vip',
            'unvip_success': 'unvip_success',
            'no_vips': 'no_vips',
            'vips_success': 'vips_success',
        },
        'chants': {
            'crowd-chant': 'crowd_chant'
        },
        'charity': {
            'charity': 'charity'
        },
        'other': {
            'cmds_available': 'cmds_available',
            'unrecognized_cmd': 'unrecognized_cmd',
            'no_permission': 'no_permission',
            'msg_ratelimit': 'rate_limit_reached_message',
        }
    }

    # MESSAGE GROUPS FOR VOD/CLIPS
    _MESSAGE_GROUPS = {
        'messages': [
            'text_message'
        ],
        'bans': [
            'ban_user'
        ],
        'deleted_messages': [
            'delete_message'
        ],
        'hosts': [
            'host_target'
        ],
        'room_states': [
            'room_state'
        ],
        'user_states': [
            'user_state'
        ],
        'notices': [
            'user_notice',
            'notice',
            'successful_login'
        ],
        'chants': [
            'crowd_chant'
        ],
        'other': [
            'clear_chat',
            'reconnect'
        ]
    }

    _MESSAGE_TYPE_REMAPPING = {}
    for _message_group in _MESSAGE_GROUP_REMAPPINGS:
        _value = _MESSAGE_GROUP_REMAPPINGS[_message_group]
        _MESSAGE_TYPE_REMAPPING.update(_value)

        if _message_group not in _MESSAGE_GROUPS:
            _MESSAGE_GROUPS[_message_group] = []
        _MESSAGE_GROUPS[_message_group] += list(_value.values())

    def _update_badge_info(self, channel):
        query = [{
            'operationName': 'ChatList_Badges',
            'variables': {
                'channelLogin': channel
            }
        }]
        data = multi_get(self._download_gql(query), 0, 'data') or {}

        badges = data.get('badges') or []
        user = multi_get(data, 'user', 'broadcastBadges') or []
        for badge in badges + user:
            setID, version, channelID = base64.b64decode(
                badge['id']).decode().strip().split(';')

            if channelID:
                if channelID not in self._SUBSCRIBER_BADGE_INFO:
                    self._SUBSCRIBER_BADGE_INFO[channelID] = {}

                self._SUBSCRIBER_BADGE_INFO[channelID][(
                    setID, version)] = badge
            else:
                self._BADGE_INFO[(setID, version)] = badge

    @staticmethod
    def _parse_item(item, offset, channel_id=None):
        info = {}

        for key in item:
            r.remap(info, TwitchChatDownloader._COMMENT_REMAPPING,
                    key, item[key])

        if 'time_in_seconds' in info:
            info['time_in_seconds'] -= offset
            info['time_text'] = seconds_to_time(int(info['time_in_seconds']))

        badges = info.pop('author_badges', None)
        if badges:
            info['author']['badges'] = [
                TwitchChatDownloader._parse_badge_info(
                    x.get('setID'), x.get('version'), channel_id)
                for x in badges
                if x.get('setID') and x.get('version')
            ]
            if not info['author']['badges']:
                del info['author']['badges']

        BaseChatDownloader._move_to_dict(info, 'author')

        original_message_type = info.get('message_type')
        if original_message_type:
            TwitchChatDownloader._set_message_type(
                info, original_message_type)
        else:
            info['message_type'] = 'text_message'

        return info

    _OPERATION_HASHES = {
        'ChatList_Badges': '86f43113c04606e6476e39dcd432dee47c994d77a83e54b732e11d4935f0cd08',
        'StreamMetadata': '1c719a40e481453e5c48d9bb585d971b8b372f8ebb105b17076722264dfa5b3e',
        'BrowsePage_Popular': 'c3322a9df3121f437182beb5a75c2a8db9a1e27fa57701ffcae70e681f502557',
        'ChannelVideoShelvesQuery': 'fb663273aa958ebe2f58d5fcb3aacc112d67ebfd7f414b095c5d1498d21aad92',
        'ClipsCards__User': 'b73ad2bfaecfd30a9e6c28fada15bd97032c83ec77a0440766a56fe0bd632777',
        'VideoMetadata': '226edb3e692509f727fd56821f5653c05740242c82b0388883e0c0e75dcbf687',
        'FilterableVideoTower_Videos': 'a937f1d22e269e39a03b509f65a7490f9fc247d7f83d6ac1421523e3b68042cb',

        'VideoCommentsByOffsetOrCursor': 'b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a',

        # Not used yet
        # 'CollectionSideBar': '27111f1b382effad0b6def325caef1909c733fe6a4fbabf54f8d491ef2cf2f14',
        # 'ChannelCollectionsContent': '07e3691a1bad77a36aba590c351180439a40baefc1c275356f40fc7082419a84',
        # 'ComscoreStreamingQuery': 'e1edae8122517d013405f237ffcc124515dc6ded82480a88daef69c83b53ac01',
        # 'VideoPreviewOverlay': '3006e77e51b128d838fa4e835723ca4dc9a05c5efd4466c1085215c6e437e65c',
    }

    def _download_base_gql(self, ops):
        return self._session_post(self._GQL_API_URL, json=ops, headers={
            'Content-Type': 'text/plain;charset=UTF-8',
            'Client-ID': self._CLIENT_ID
        }).json()

    def _download_gql(self, ops):
        for op in ops:
            op['extensions'] = {
                'persistedQuery': {
                    'version': 1,
                    'sha256Hash': self._OPERATION_HASHES[op['operationName']],
                }
            }
        return self._download_base_gql(ops)

    _GAME_REMAPPING = {
        'id': 'id',
        'name': 'name',
        'displayName': 'display_name',
        'boxArtURL': 'box_art_url'
    }

    @staticmethod
    def _parse_game(item):
        if isinstance(item, dict):
            return r.remap_dict(item, TwitchChatDownloader._GAME_REMAPPING)
        return None

    _CLIP_REMAPPING = {
        'id': r('id', str_or_none),
        'slug': 'slug',
        'url': 'url',
        'embedURL': 'embed_url',
        'title': 'title',
        'viewCount': 'views',
        'language': 'language',
        'curator': r('curator', _parse_user),
        'game': r('game', _parse_game),
        'language': 'language',
        'broadcaster': r('broadcaster', _parse_user),

        'thumbnailURL': 'thumbnail_url',
        'createdAt': r('created_at', timestamp_to_microseconds),
        'durationSeconds': 'duration',


    }

    def get_user_clips(self, username, limit=100, filter_by='LAST_WEEK'):
        # filter_by:
        # LAST_WEEK
        # LAST_DAY
        # LAST_MONTH
        # ALL_TIME

        # offset= 20# , offset = 0

        remaining_count = limit
        offset = 0
        while True:
            num_to_get = max(min(remaining_count, 100), 0)  # in this call
            if num_to_get <= 0:
                break

            query = [{
                'operationName': 'ClipsCards__User',
                'variables': {
                    'cursor': base64.b64encode(str(offset).encode()).decode(),
                    'login': username,
                    'limit': num_to_get,
                    'criteria': {
                        'filter': filter_by
                    }
                }
            }]
            info = self._download_gql(query)
            if not info:
                break

            clips = info[0]['data']['user']['clips']

            edges = clips['edges']
            remaining_count -= len(edges)

            for edge in edges:
                node = edge['node'] or {}
                yield r.remap_dict(node, TwitchChatDownloader._CLIP_REMAPPING)

            if not clips['pageInfo']['hasNextPage']:
                break

    _VIDEO_REMAPPING = {
        'id': r('id', str_or_none),
        'animatedPreviewURL': 'animated_preview_url',
        'game': r('game', _parse_game),

        'lengthSeconds': 'duration',

        'owner': r('owner', _parse_user),

        'previewThumbnailURL': 'preview_thumbnail_url',

        'publishedAt': r('published_at', timestamp_to_microseconds),

        'title': 'title',
        'viewCount': 'views',
        'resourceRestriction': 'resource_restriction'

        # 'contentTags': 'tags'
    }

    def get_user_videos(self, username, limit=None, video_type=None, sort='TIME'):
        # Name -> broadcastType

        # Collections (ChannelCollectionsContent)
        #

        # Past broadcasts -> ARCHIVE
        # Highlights -> HIGHLIGHT
        # Uploads -> UPLOAD
        # Past premieres -> PAST_PREMIERE
        # All Videos -> null

        # Sort -> videoSort
        # VIEWS
        # TIME
        if limit is None:
            limit = float('inf')

        remaining_count = limit
        cursor = None

        while True:
            num_to_get = max(min(remaining_count, 30), 0)  # in this call
            if num_to_get <= 0:
                break

            query = [{
                'operationName': 'FilterableVideoTower_Videos',
                'variables': {
                    'limit': num_to_get,
                    'channelOwnerLogin': username,
                    'broadcastType': video_type,
                    'videoSort': sort
                }
            }]
            if cursor:
                query[0]['variables']['cursor'] = cursor

            info = self._download_gql(query)
            if not info:
                break

            videos = multi_get(info, 0, 'data', 'user', 'videos')

            if not videos:
                break

            edges = videos['edges']
            remaining_count -= len(edges)

            for edge in edges:
                cursor = edge.get('cursor')
                node = edge.get('node')
                if not node:
                    continue
                yield r.remap_dict(node, TwitchChatDownloader._VIDEO_REMAPPING)

            if not videos['pageInfo']['hasNextPage']:
                break

    def get_featured_videos(self, username):
        query = [{
            'operationName': 'ChannelVideoShelvesQuery',
            'variables': {
                'channelLogin': username,
                'first': 5
            }
        }]
        edges = self._download_gql(
            query)[0]['data']['user']['videoShelves']['edges']
        return edges

    _LIVESTREAM_REMAPPING = {

        'id': r('id', str_or_none),
        'title': 'title',
        'viewersCount': 'viewers',

        'previewImageURL': 'preview_image_url',
        'broadcaster': r('broadcaster', _parse_user),
        'game': r('game', _parse_game),


        # 'tags': 'tags'

        'type': 'type'  # e.g. 'live'
    }

    def get_top_livestreams(self, limit=30):
        remaining_count = limit

        cursor = ''

        while True:
            num_to_get = max(min(remaining_count, 30), 0)
            if num_to_get <= 0:
                break

            query = [{
                'operationName': 'BrowsePage_Popular',
                'variables': {
                    'limit': num_to_get,
                    'cursor': cursor,
                    'platformType': 'all',
                    'options': {
                        'sort': 'VIEWER_COUNT'  # RECENT, RELEVANCE, VIEWER_COUNT_ASC
                    },
                    'sortTypeIsRecency': False
                }
            }]
            edges = self._download_gql(query)[0]['data']['streams']['edges']

            cursor = edges[-1]['cursor']
            remaining_count -= num_to_get

            for edge in edges:
                node = edge['node'] or {}
                yield r.remap_dict(node, TwitchChatDownloader._LIVESTREAM_REMAPPING)

    _TWITCH_HOME = 'https://www.twitch.tv'
    _TWITCH_VIDEOS = 'https://www.twitch.tv/videos'

    def generate_urls(self, livestream_limit, vod_limit, clip_limit, **kwargs):
        # max_tests = livestream_limit + livestream_limit*(vod_limit+clip_limit)

        num_vods = math.ceil(
            vod_limit/livestream_limit) if livestream_limit > 0 else vod_limit
        num_clips = math.ceil(
            clip_limit/livestream_limit) if livestream_limit > 0 else clip_limit

        livestreams = self.get_top_livestreams(livestream_limit)
        for livestream in livestreams:
            name = livestream['broadcaster']['name']

            # e.g. https://www.twitch.tv/shroud
            yield f'{self._TWITCH_HOME}/{name}'

            vods = self.get_user_videos(name, num_vods)
            for vod in vods:
                # e.g. https://www.twitch.tv/videos/12345678
                yield f"{self._TWITCH_VIDEOS}/{vod['id']}"

            clips = self.get_user_clips(name, num_clips)
            for clip in clips:
                # e.g. https://clips.twitch.tv/FastThankfulLobsterEagleEye-SFi4SJWaTkAYu-B3
                yield clip['url']

    # offset and max_duration are used by clips

    def _get_chat_messages_by_vod_id(self, vod_id, params, max_duration, offset=None):

        # twitch does not provide messages before the stream starts,
        # so we default to a start time of 0
        start_time = ensure_seconds(
            params.get('start_time'), 0)

        e_time = params.get('end_time')
        if offset is None:  # is a vod
            offset = 0
            end_time = ensure_seconds(e_time)
            content_offset_seconds = min(start_time, max_duration)

        else:  # is a clip
            # do not allow for end_time to be None
            end_time = ensure_seconds(e_time, max_duration)
            content_offset_seconds = (start_time or 0) + offset

        max_attempts = params.get('max_attempts')

        messages_groups_to_add = params.get('message_groups') or []
        messages_types_to_add = params.get('message_types') or []

        # api_url = self._API_TEMPLATE.format(vod_id, self._CLIENT_ID)

        message_count = 0
        # do not need inactivity timeout (not live)

        cursor = ''
        while True:
            variables = {
                'videoID': vod_id,
            }

            if cursor:
                variables['cursor'] = cursor
            else:
                variables['contentOffsetSeconds'] = content_offset_seconds

            query = [{
                'operationName': 'VideoCommentsByOffsetOrCursor',
                'variables': variables
            }]

            for attempt_number in attempts(max_attempts):
                try:
                    info = self._download_gql(query)[0]['data']['video']
                    break
                except (JSONDecodeError, RequestException) as e:
                    self.retry(attempt_number, error=e, **params)

            comments = info.get('comments')
            if not comments:
                break

            # Used for custom badge retrieval
            creator_channel_id = multi_get(info, 'creator', 'channel', 'id')

            edges = comments.get('edges') or []

            for edge in edges:
                cursor = edge.get('cursor')
                node = edge.get('node')
                if not node:
                    continue

                data = self._parse_item(node, offset, creator_channel_id)

                # test for missing keys
                missing_keys = data.keys() - TwitchChatDownloader._KNOWN_COMMENT_KEYS

                if missing_keys:
                    debug_log(
                        f'Missing keys found: {missing_keys}',
                        f'Original data: {node}',
                        f'Parsed data: {data}',
                        node.keys(),
                        TwitchChatDownloader._KNOWN_COMMENT_KEYS
                    )

                time_in_seconds = data.get('time_in_seconds', 0)

                before_start = start_time is not None and time_in_seconds < start_time
                after_end = end_time is not None and time_in_seconds > end_time

                if before_start:  # still getting to messages
                    continue
                elif after_end:  # after end
                    return  # while actually searching, if time is invalid

                to_add = self._must_add_item(
                    data,
                    self._MESSAGE_GROUPS,
                    messages_groups_to_add,
                    messages_types_to_add
                )

                if not to_add:
                    continue

                message_count += 1
                yield data

            log('debug', f'Total number of messages: {message_count}')

            if not comments['pageInfo']['hasNextPage']:
                break

    def _get_chat_by_vod_id(self, match, params):
        return self.get_chat_by_vod_id(match.group('id'), params)

    def get_chat_by_vod_id(self, vod_id, params):
        max_attempts = params.get('max_attempts')

        query = [{
            'operationName': 'VideoMetadata',
            'variables': {
                'channelLogin': '',
                'videoID': vod_id
            }
        }]

        for attempt_number in attempts(max_attempts):
            try:
                video = self._download_gql(query)[0]['data']['video']
                break
            except (JSONDecodeError, RequestException, KeyError) as e:
                self.retry(attempt_number, error=e, **params)

        if not video:
            raise VideoUnavailable(
                "Sorry. Unless you've got a time machine, that content is unavailable.")
        title = video.get('title')
        duration = video.get('lengthSeconds')

        channel_name = multi_get(video, 'owner', 'login')
        self._update_badge_info(channel_name)

        return Chat(
            self._get_chat_messages_by_vod_id(
                vod_id, params, duration),
            title=title,
            duration=duration,
            status='past',
            video_type='video',
            id=vod_id
        )

    def _get_chat_by_clip_id(self, match, params):
        return self.get_chat_by_clip_id(match.group('id'), params)

    def get_chat_by_clip_id(self, clip_id, params):

        max_attempts = params.get('max_attempts')

        query = {
            'query': '{ clip(slug: "%s") { broadcaster { id login } video { id createdAt } createdAt durationSeconds videoOffsetSeconds title url slug } }' % clip_id,
        }

        for attempt_number in attempts(max_attempts):
            try:
                clip = self._download_base_gql(query)['data']['clip']
                break
            except (JSONDecodeError, RequestException) as e:
                self.retry(attempt_number, error=e, **params)

        vod_id = multi_get(clip, 'video', 'id')

        if vod_id is None:
            raise NoChatReplay(
                "This clip's past broadcast has expired and chat replay is no longer available.")

        offset = clip.get('videoOffsetSeconds')

        duration = clip.get('durationSeconds')
        title = f"{clip.get('title')} ({clip_id})"

        channel_name = multi_get(clip, 'broadcaster', 'login')
        self._update_badge_info(channel_name)

        return Chat(
            self._get_chat_messages_by_vod_id(
                vod_id, params, duration, offset),
            title=title,
            duration=duration,
            status='past',
            video_type='clip',
            id=clip_id
        )

    _MESSAGE_REGEX = re.compile(
        r'^@(.+?(?=\s+:)).*tmi\.twitch\.tv\s+(\S+)(?:[^#\r\n]+#)?\s(?:\S+)?(?:\s:([^\r\n]*))?', re.MULTILINE)
    # Groups:
    # 1. Tag info
    # 2. Action type
    # 3. Message

    _BADGE_KEYS = ('title', 'image1x', 'image2x',
                   'image4x', 'clickAction', 'clickURL')

    @staticmethod
    def _parse_badge_info(name, version, channel_id=None):
        new_badge = {
            'name': replace_with_underscores(name),
            'version': int_or_none(version, version)
        }

        # prioritise custom emotes (e.g. subscriber and bits)
        new_badge_info = None
        if channel_id is not None:
            new_badge_info = multi_get(
                TwitchChatDownloader._SUBSCRIBER_BADGE_INFO, str(channel_id), (name, version))

        if not new_badge_info:
            new_badge_info = multi_get(
                TwitchChatDownloader._BADGE_INFO, (name, version))

        if new_badge_info:
            for key in TwitchChatDownloader._BADGE_KEYS:
                new_badge[key] = new_badge_info.get(key)

            image_urls = [
                (new_badge.pop(f'image{i}x', ''), i * 18) for i in (1, 2, 4)]

            new_badge['icons'] = []
            for image_url, size in image_urls:
                new_badge['icons'].append(Image(image_url, size, size).json())

        return new_badge

    @staticmethod
    def _parse_irc_badges(badges, channel_id):
        info = []
        if not badges:
            return info

        for badge in badges.split(','):
            split = badge.split('/', 1)
            key_length = len(split)
            if key_length == 1:
                # If there's no /, we assign a value of None (null).
                split.append(None)

            info.append(TwitchChatDownloader._parse_badge_info(
                split[0], split[1], channel_id))
        return info

    @staticmethod
    def _set_message_type(info, original_message_type):
        new_message_type = TwitchChatDownloader._MESSAGE_TYPE_REMAPPING.get(
            original_message_type)

        if new_message_type:
            info['message_type'] = new_message_type
        else:
            debug_log(
                f'Unknown message type: {original_message_type}',
                f'Parsed data: {info}'
            )

    @staticmethod
    def _add_text_for_emotes(message, emote_list):
        for emote in emote_list:
            try:
                first_location = list(
                    map(lambda x: int(x), emote['locations'][0].split('-')))
                emote['name'] = message[first_location[0]:first_location[1] + 1]
            except Exception:
                debug_log(
                    f'Invalid emote: {emote}',
                    f'Message: {message}'
                )
                continue

    @staticmethod
    def _parse_irc_item(match):
        info = {}

        split_info = match.group(1).split(';')

        for item in split_info:
            keys = item.split('=', 1)
            key_length = len(keys)
            if key_length == 1:
                # If there's no equals, we assign the tag a value of true.
                keys.append(True)
            elif key_length == 2:
                pass
            else:  # TODO never reaches this
                debug_log(
                    f'Invalid item found: {item}.',
                    f'All items: {split_info}.',
                )
                continue

            r.remap(info, TwitchChatDownloader._IRC_REMAPPING,
                    keys[0], keys[1], keep_unknown_keys=True, replace_char_with_underscores='-')

        message_match = match.group(3)
        if message_match:
            info['message'] = remove_prefixes(message_match, '\u0001ACTION ')

            emotes = info.pop('emotes', None)
            if emotes:
                TwitchChatDownloader._add_text_for_emotes(
                    info['message'], emotes)
                info['emotes'] = emotes

        author_badge_metadata = info.pop('author_badge_metadata', [])
        author_badges = info.pop('author_badges', [])

        info['author_badges'] = TwitchChatDownloader._parse_irc_badges(
            author_badges, info.get('channel_id'))

        badge_metadata = TwitchChatDownloader._parse_irc_badges(
            author_badge_metadata, info.get('channel_id'))

        subscriber_badge = next(
            (x for x in info['author_badges'] if x.get('name') == 'subscriber'), None)
        subscriber_badge_metadata = next(
            (x for x in badge_metadata if x.get('name') == 'subscriber'), None)
        if subscriber_badge and subscriber_badge_metadata:
            subscriber_badge['months'] = int_or_none(
                subscriber_badge_metadata['version'], 0)

        author_display_name = info.get('author_display_name')
        if author_display_name:
            info['author_name'] = author_display_name.lower()

        in_reply_to = BaseChatDownloader._move_to_dict(info, 'in_reply_to')

        BaseChatDownloader._move_to_dict(in_reply_to, 'author')
        BaseChatDownloader._move_to_dict(info, 'author')

        original_action_type = match.group(2)

        if original_action_type:
            new_action_type = TwitchChatDownloader._ACTION_TYPE_REMAPPING.get(
                original_action_type)
            if new_action_type:
                info['action_type'] = new_action_type
            else:
                # unknown action type
                info['action_type'] = original_action_type
                debug_log([
                    f"Unknown action type: {info['action_type']}",
                    match,
                    info
                ])

        original_message_type = info.get('message_type')
        if original_message_type:
            TwitchChatDownloader._set_message_type(
                info, original_message_type)
        else:
            info['message_type'] = info['action_type']

        if original_action_type == 'CLEARCHAT':
            if message_match:  # is a ban
                info['message_type'] = 'ban_user'
                info['ban_type'] = 'timeout' if info.get(
                    'ban_duration') else 'permanent'
                info['banned_user'] = info.pop('message', '')

            else:  # did /clearchat
                pass

        follower_only = info.get('follower_only')
        if follower_only:
            info['follower_only'] = follower_only != -1
            if follower_only > 0:
                info['minutes_to_follow_before_chatting'] = follower_only

        slow_mode = info.get('slow_mode')
        if slow_mode is not None:
            if slow_mode != 0:
                info['slow_mode'] = True
                info['seconds_to_wait'] = slow_mode
            else:
                info['slow_mode'] = False

        # TODO
        # :tmi.twitch.tv HOSTTARGET #gothamchess :anna_chess 6612
        return info

    def _get_chat_messages_by_stream_id(self, stream_id, params):
        max_attempts = params.get('max_attempts')

        message_receive_timeout = params.get('message_receive_timeout')

        buffer_size = params.get('buffer_size')

        messages_groups_to_add = params.get('message_groups') or []
        messages_types_to_add = params.get('message_types') or []

        def create_connection():
            for attempt_number in attempts(max_attempts):
                try:
                    irc = TwitchChatIRC()
                    irc.set_timeout(message_receive_timeout)
                    irc.join_channel(stream_id)
                    return irc
                except (socket.gaierror, ConnectionRefusedError) as e:
                    self.retry(attempt_number, error=e, **params)

        twitch_chat_irc = create_connection()

        last_ping_time = time.time()

        # TODO make this a param
        ping_every = 60  # how often to ping the server

        readbuffer = ''

        message_count = 0

        try:
            while True:

                try:
                    new_info = twitch_chat_irc.recv(buffer_size)

                    if not new_info:
                        raise ConnectionError('Lost connection, reconnecting.')

                    readbuffer += new_info

                    if self._PING_TEXT in readbuffer:
                        twitch_chat_irc.send_raw(self._PONG_TEXT)

                    matches = list(self._MESSAGE_REGEX.finditer(readbuffer))
                    full_readbuffer = readbuffer.endswith('\r\n')
                    if matches:
                        if not full_readbuffer:
                            # sometimes a buffer does not contain a full message
                            # last one is incomplete

                            span = matches[-1].span()

                            pass_on = readbuffer[span[0]:]

                            # check whether message was cut off
                            if '\r\n' in pass_on:  # last message not matched
                                # only pass on incomplete message

                                # readbuffer[span[1]:]
                                pass_on = pass_on[span[1] - span[0]:]

                            # actual message cut off (matched, but not complete)
                            else:
                                # remove the last match from being processed (as it is incomplete)
                                matches.pop()

                            # pass remaining information to next attempt
                            readbuffer = pass_on

                        else:
                            # the whole readbuffer was read correctly.
                            # reset the readbuffer
                            readbuffer = ''

                        for match in matches:

                            data = self._parse_irc_item(match)

                            # test for missing keys
                            missing_keys = data.keys() - TwitchChatDownloader._KNOWN_IRC_KEYS

                            if missing_keys:
                                debug_log(
                                    f'Missing keys found: {missing_keys}',
                                    f'Original data: {match.groups()}',
                                    f'Parsed data: {data}'
                                )
                            # check whether to skip this message or not, based on its type

                            to_add = self._must_add_item(
                                data,
                                self._MESSAGE_GROUPS,
                                messages_groups_to_add,
                                messages_types_to_add
                            )

                            if not to_add:
                                continue

                            message_count += 1
                            yield data

                        log('debug',
                            f'Total number of messages: {message_count}')

                    elif full_readbuffer:
                        # No matches, but data has been read successfully.
                        # This means that we can safely reset the readbuffer.
                        # This is used to periodically reset the readbuffer,
                        # to avoid a massive buffer from forming.

                        # never pause
                        log('debug',
                            f'No matches found in "\n{readbuffer.strip()}\n"')
                        readbuffer = ''

                    current_time = time.time()

                    time_since_last_ping = current_time - last_ping_time

                    if time_since_last_ping > ping_every:
                        twitch_chat_irc.send_raw('PING')
                        last_ping_time = current_time

                except socket.timeout:
                    pass  # Allows for keyboard interrupts

                except ConnectionError:
                    # Close old connection
                    twitch_chat_irc.close_connection()

                    # Create a new connection
                    twitch_chat_irc = create_connection()

        finally:
            twitch_chat_irc.close_connection()

    def _get_chat_by_stream_id(self, match, params):
        return self.get_chat_by_stream_id(match.group('id'), params)

    def get_chat_by_stream_id(self, stream_id, params):

        max_attempts = params.get('max_attempts')

        query = [{
            'operationName': 'StreamMetadata',
            'variables': {'channelLogin': stream_id.lower()}
        }]

        for attempt_number in attempts(max_attempts):
            try:
                stream_info = self._download_gql(query)[0]['data']['user']
                break
            except (JSONDecodeError, RequestException) as e:
                self.retry(attempt_number, error=e, **params)

        if not stream_info:
            raise UserNotFound(f'Unable to find user: "{stream_id}"')

        is_live = multi_get(stream_info, 'stream', 'type') == 'live'
        channel_id = multi_get(stream_info, 'channel', 'id')
        title = multi_get(stream_info, 'lastBroadcast',
                          'title') if is_live else stream_id

        self._update_badge_info(stream_id)

        return Chat(
            self._get_chat_messages_by_stream_id(
                stream_id, params),
            title=title,
            duration=None,
            status='live' if is_live else 'upcoming',  # Always live or upcoming
            video_type='video',
            id=stream_id
        )

    # # e.g. 'https://www.twitch.tv/spamfish/videos?filter=all'
    # _VALID_VIDEOS_URL = r'https?://(?:(?:www|go|m)\.)?twitch\.tv/(?P<id>[^/]+)/(?:videos|profile)'

    # # e.g. 'https://www.twitch.tv/vanillatv/clips?filter=clips&range=all'
    # _VALID_VIDEO_CLIPS_URL = r'https?://(?:(?:www|go|m)\.)?twitch\.tv/(?P<id>[^/]+)/(?:clips|videos/*?\?.*?\bfilter=clips)'

    # # e.g. 'https://www.twitch.tv/collections/wlDCoH0zEBZZbQ'
    # _VALID_COLLECTIONS_URL = r'https?://(?:(?:www|go|m)\.)?twitch\.tv/collections/(?P<id>[^/]+)'
