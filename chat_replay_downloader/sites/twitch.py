import re
import json
import time
import socket

from .common import ChatDownloader

from ..errors import (
    TwitchError,
    CallbackFunction,
    InvalidParameter
)

from ..utils import (
    ensure_seconds,
    timestamp_to_microseconds,
    seconds_to_time,
    try_get,
    int_or_none,
    replace_with_underscores,
    try_get_first_key,
    debug_print,
    multi_get,
    update_dict_without_overwrite
)

# TODO export as another module?


class TwitchChatIRC():
    _CURRENT_CHANNEL = None

    def __init__(self):
        # create new socket
        self._SOCKET = socket.socket()

        # start connection
        self._SOCKET.connect(('irc.chat.twitch.tv', 6667))
        # print('Connected to', self._HOST, 'on port', self._PORT)

        # https://dev.twitch.tv/docs/irc/tags
        # https://dev.twitch.tv/docs/irc/membership
        # https://dev.twitch.tv/docs/irc/commands

        # twitch.tv/membership
        self.send_raw(
            'CAP REQ :twitch.tv/tags twitch.tv/commands twitch.tv/membership')
        self.send_raw('PASS SCHMOOPIIE')
        self.send_raw('NICK justinfan67420')

    def send_raw(self, string):
        self._SOCKET.send((string+'\r\n').encode('utf-8'))

    def recvall(self, buffer_size):
        data = b''
        while True:
            part = self._SOCKET.recv(buffer_size)
            data += part

            # attempt to decode this, otherwise the last byte was incomplete
            # in this case, get more data
            try:
                return data.decode('utf-8')  # if len(part) < buffer_size:
            except UnicodeDecodeError:
                # print('error', data)
                continue

                # break
        # print(data)
        # TODO perhaps, on decode error, continue receiving
        return  # ignore needed for times when message is split

    def join_channel(self, channel_name):
        channel_lower = channel_name.lower()

        if(self._CURRENT_CHANNEL != channel_lower):
            self.send_raw('JOIN #{}'.format(channel_lower))
            self._CURRENT_CHANNEL = channel_lower

    def set_timeout(self, message_receive_timeout):
        self._SOCKET.settimeout(message_receive_timeout)

    def close_connection(self):
        self._SOCKET.close()

        # except KeyboardInterrupt:
        # 	print('Interrupted by user.')

        # except Exception as e:
        # 	print('Unknown Error:',e)
        # 	raise e

        # return messages


class TwitchChatDownloader(ChatDownloader):
    _BADGE_INFO = {}
    _BADGE_INFO_URL = 'https://badges.twitch.tv/v1/badges/global/display'
    # TODO add local version of badge list?

    def __init__(self, updated_init_params={}):
        super().__init__(updated_init_params)
        # self._name = None
        # self.name = 'Twitch.tv'

        TwitchChatDownloader._BADGE_INFO = self._session_get_json(
            self._BADGE_INFO_URL).get('badge_sets') or {}
        # print(TwitchChatDownloader._BADGE_INFO.keys(), flush=True)
        # #exit()
        # # print(TwitchChatDownloader._BADGE_INFO)
        #

    def __str__(self):
        return 'Twitch.tv'

    # clips
    # vod
    # name -> live

    _VALID_URL = r'https?://(?:(?:www|go|m|clips)\.)?twitch\.tv'

    # e.g. 'http://www.twitch.tv/riotgames/v/6528877?t=5m10s'
    _VALID_VOD_URL = r'''(?x)
                    https?://
                        (?:
                            (?:(?:www|go|m)\.)?twitch\.tv/(?:[^/]+/v(?:ideo)?|videos)/|
                            player\.twitch\.tv/\?.*?\bvideo=v?
                        )
                        (?P<id>\d+)
                    '''

    # e.g. 'https://clips.twitch.tv/FaintLightGullWholeWheat'
    _VALID_CLIPS_URL = r'''(?x)
                        https?://
                            (?:
                                clips\.twitch\.tv/(?:embed\?.*?\bclip=|(?:[^/]+/)*)|
                                (?:(?:www|go|m)\.)?twitch\.tv/[^/]+/clip/
                            )
                            (?P<id>[^/?#&]+)
                        '''

    # e.g. 'http://www.twitch.tv/shroomztv'
    _VALID_STREAM_URL = r'''(?x)
                        https?://
                            (?:
                                (?:(?:www|go|m)\.)?twitch\.tv/|
                                player\.twitch\.tv/\?.*?\bchannel=
                            )
                            (?P<id>[^/#?]+)
                        '''

    _CLIENT_ID = 'kimne78kx3ncx6brgo4mv6wki5h1ko'  # public client id

    _GQL_API_URL = 'https://gql.twitch.tv/gql'
    _API_TEMPLATE = 'https://api.twitch.tv/v5/videos/{}/comments?client_id={}'

    _SUBSCRIPTION_TYPES = {
        'Prime': 'Prime',
        '1000': 'Tier 1',
        '2000': 'Tier 2',
        '3000': 'Tier 3'
    }

    _REMAP_FUNCTIONS = {
        'parse_timestamp': timestamp_to_microseconds,  # lambda x :  * 1000,
        'get_body': lambda x: x.get('body'),
        'parse_author_images': lambda x: TwitchChatDownloader.parse_author_images(x),

        'parse_badges': lambda x: TwitchChatDownloader.parse_badges(x),

        'multiply_by_1000': lambda x: int_or_none(x) * 1000,
        'parse_int': int_or_none,
        'parse_bool': lambda x: x == '1',

        'replace_with_underscores': replace_with_underscores,


        'parse_subscription_type': lambda x: TwitchChatDownloader._SUBSCRIPTION_TYPES.get(x)

    }

    _REMAPPING = {
        # 'origID' : ('mapped_id', 'remapping_function')
        '_id': 'id',
        'created_at': ('timestamp', 'parse_timestamp'),
        'commenter': 'author_info',

        'content_offset_seconds': 'time_in_seconds',




        'source': 'source',
        'state': 'state',
        # TODO make sure body vs. fragments okay
        'message': ('message', 'get_body'),

        'name': 'author_name',
        'display_name': 'author_display_name',
        'logo': ('author_images', 'parse_author_images'),


        'type': 'author_type',


        # TODO 'type' # author type?
    }

    @staticmethod
    def parse_author_images(original_url):
        smaller_icon = original_url.replace('300x300', '70x70')
        return [
            ChatDownloader.create_image(original_url, 300, 300),
            ChatDownloader.create_image(smaller_icon, 70, 70),
        ]
        # -70x70

        #         "author_images": [
        #     {
        #         "height": 32,
        #         "url": "https://yt3.ggpht.com/ytc/AAUvwniAWKgW_6aBJ8jPx_a1jlUo_8bh0WULv7sXYw=s32-c-k-c0xffffffff-no-rj-mo",
        #         "width": 32
        #     },
        #     {
        #         "height": 64,
        #         "url": "https://yt3.ggpht.com/ytc/AAUvwniAWKgW_6aBJ8jPx_a1jlUo_8bh0WULv7sXYw=s64-c-k-c0xffffffff-no-rj-mo",
        #         "width": 64
        #     }
        # ],

    @ staticmethod
    def _parse_item(item, offset=0):
        info = {}
        # info is starting point
        for key in item:
            ChatDownloader.remap(info, TwitchChatDownloader._REMAPPING,
                                 TwitchChatDownloader._REMAP_FUNCTIONS, key, item[key])

        if 'time_in_seconds' in info:
            info['time_in_seconds'] -= offset
            info['time_text'] = seconds_to_time(int(info['time_in_seconds']))

        author_info = info.pop('author_info', None)
        if author_info:
            update_dict_without_overwrite(
                info, TwitchChatDownloader._parse_item(author_info))

        return info

    _REGEX_FUNCTION_MAP = [
        (_VALID_VOD_URL, 'get_chat_by_vod_id'),
        (_VALID_CLIPS_URL, 'get_chat_by_clip_id'),
        (_VALID_STREAM_URL, 'get_chat_by_stream_id'),
    ]

    # offset and max_duration are used by clips
    def get_chat_by_vod_id(self, vod_id, params, offset=0, max_duration=None):
        #print('get_chat_by_vod_id:', vod_id)

        start_time = ensure_seconds(
            self.get_param_value(params, 'start_time'), 0)

        # twitch does not provide messages before the stream starts,
        # so we default to a start time of 0
        end_time = ensure_seconds(
            self.get_param_value(params, 'end_time'), max_duration)

        max_attempts = self.get_param_value(params, 'max_attempts')
        max_messages = self.get_param_value(params, 'max_messages')
        message_list = self.get_param_value(params, 'messages')
        callback = self.get_param_value(params, 'callback')

        invalid_message_groups = 'messages' not in (
            self.get_param_value(params, 'message_groups') or [])
        invalid_message_types = 'text_message' not in (
            self.get_param_value(params, 'message_types') or [])
        if invalid_message_groups and invalid_message_types:
            raise InvalidParameter('Custom method types/groups are not supported for Twitch VODs/clips')

        api_url = self._API_TEMPLATE.format(vod_id, self._CLIENT_ID)

        # api calls start here
        content_offset_seconds = (start_time or 0) + offset

        cursor = ''
        while True:
            url = '{}&cursor={}&content_offset_seconds={}'.format(
                api_url, cursor, content_offset_seconds)

            # TODO use max attempts
            info = self._session_get_json(url)
            # print(info)
            error = info.get('error')

            if(error):
                # TODO make parse error and raise more general errors
                raise TwitchError(info.get('message'))

            for comment in info.get('comments') or []:
                data = self._parse_item(comment, offset).copy()

                time_in_seconds = data.get('time_in_seconds', 0)
                #print('\t',time_in_seconds, start_time, end_time)

                before_start = start_time is not None and time_in_seconds < start_time
                after_end = end_time is not None and time_in_seconds > end_time

                if(before_start):  # still getting to messages
                    continue
                elif(after_end):  # after end
                    return message_list  # while actually searching, if time is invalid

                # TODO if correct message type
                message_list.append(data)

                self.perform_callback(callback, data)

            cursor = info.get('_next')

            if not cursor:  # no more
                return message_list

    def get_chat_by_clip_id(self, clip_id, params):
        print('get_chat_by_clip_id:', clip_id)
        query = {
            'query': '{ clip(slug: "%s") { video { id createdAt } createdAt durationSeconds videoOffsetSeconds title url slug } }' % clip_id,
        }
        clip = self._session_post(self._GQL_API_URL,
                                  data=json.dumps(query).encode(),
                                  headers={'Client-ID': self._CLIENT_ID})['data']['clip']

        # TODO error checking
        # print(clip)

        vod_id = try_get(clip, lambda x: x['video']['id'])
        offset = clip.get('videoOffsetSeconds')
        duration = clip.get('durationSeconds')

        #print(vod_id, offset, duration)

        return self.get_chat_by_vod_id(vod_id, params, offset, duration)

    # e.g. @badge-info=;badges=;client-nonce=c5fbf6b9f6b249353811c21dfffe0321;color=#FF69B4;display-name=sumz5;emotes=;flags=;id=340fec40-f54c-4393-a044-bf62c636e98b;mod=0;room-id=86061418;subscriber=0;tmi-sent-ts=1607447245754;turbo=0;user-id=611966876;user-type= :sumz5!sumz5@sumz5.tmi.twitch.tv PRIVMSG #5uppp :PROXIMITY?

    _MESSAGE_REGEX = re.compile(
        r'^@(.+?(?=\s+:))(?:\s\S*?)tmi\.twitch\.tv\s+(\S+)\s+#?\S+\s+?\:?([^\r\n]*)?', re.MULTILINE)
    # Groups:
    # 1. Tag info
    # 2. Action type
    # 3. Message

    # A full list can be found here: https://twitchinsights.net/badges
    # https://badges.twitch.tv/v1/badges/global/display

    _BADGE_KEYS = ('title', 'description', 'image_url_1x',
                   'image_url_2x', 'image_url_4x', 'click_action', 'click_url')
    _BADGE_ID_REGEX = r'v1/(.+)/'

    @staticmethod
    def parse_badges(badge_info):
        info = []
        if(not badge_info):
            return info

        for badge in badge_info.split(','):
            split = badge.split('/')
            new_badge = {
                'type': replace_with_underscores(split[0]),
                'version': int_or_none(split[1], split[1])
            }

            # TODO skip for subscribers? - different per channel
            # check for additional information
            new_badge_info = multi_get(
                TwitchChatDownloader._BADGE_INFO, split[0], 'versions', split[1]) or {}

            if new_badge_info:
                for key in TwitchChatDownloader._BADGE_KEYS:
                    new_badge[key] = new_badge_info.get(key)

                # TODO create image with icons (diff sizes)
                # image_url_1x image_url_2x image_url_4x
                # 18px x 18px, 36px x 36px, and 72px x 72px.

                image_urls = [(new_badge.pop('image_url_{}x'.format(
                    i[0]), ''), i[1]) for i in ((1, 18), (2, 36), (3, 72))]
                if image_urls:
                    new_badge['icons'] = []

                for image_url, size in image_urls:
                    new_badge['icons'].append(
                        ChatDownloader.create_image(image_url, size, size))

                if image_urls:
                    badge_id = re.search(
                        TwitchChatDownloader._BADGE_ID_REGEX, image_urls[0][0] or '')
                    if(badge_id):
                        new_badge['badge_id'] = badge_id.group(1)

            info.append(new_badge)
        return info

    _IRC_REMAPPING = {
        # CLEARCHAT
        # Purges all chat messages in a channel, or purges chat messages from a specific user, typically after a timeout or ban.
        # (Optional) Duration of the timeout, in seconds. If omitted, the ban is permanent.
        'ban-duration': ('ban_duration', 'parse_int'),

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
        'user-id': 'author_id',
        # 'message': 'message', # The message.



        # PRIVMSG
        'badge-info': ('author_badge_metadata', 'parse_badges'),
        'badges': ('author_badges', 'parse_badges'),



        'bits': ('bits', 'parse_int'),

        # TODO change formatting to:
        # 'id': 'message_id'

        'id': 'message_id',
        # (, 'do_nothing'), #already included in badges
        'mod': ('is_moderator', 'parse_bool'),
        'room-id': 'channel_id',

        'tmi-sent-ts': ('timestamp', 'multiply_by_1000'),


        # ROOMSTATE
        'emote-only': ('emote_only', 'parse_bool'),
        'followers-only': ('follower_only', 'parse_int'),

        # TODO followers only and slow mode make separate values for duration

        'r9k': ('r9k_mode', 'parse_bool'),
        'slow': ('slow_mode', 'parse_int'),
        'subs-only': ('subscriber_only', 'parse_bool'),

        # USERNOTICE
        'msg-id': 'message_type',  # (, 'replace_with_underscores'),

        'system-msg': 'system_message',

        # USERNOTICE - other
        'msg-param-cumulative-months': ('months', 'parse_int'),
        'msg-param-months': ('months', 'parse_int'),
        'msg-param-displayName': 'raider_display_name',
        'msg-param-login': 'raider_name',
        'msg-param-viewerCount': 'number_of_raiders',

        'msg-param-promo-name': 'promo_name',
        'msg-param-promo-gift-total': 'number_of_gifts_given_during_promo',

        'msg-param-recipient-id': 'gift_recipient_id',
        'msg-param-recipient-user-name': 'gift_recipient_display_name',
        'msg-param-recipient-display-name': 'gift_recipient_display_name',
        'msg-param-gift-months': ('number_of_months_gifted', 'parse_int'),

        'msg-param-sender-login': 'gifter_name',
        'msg-param-sender-name': 'gifter_display_name',

        'msg-param-should-share-streak': ('user_wants_to_share_streaks', 'parse_bool'),
        'msg-param-streak-months': ('number_of_consecutive_months_subscribed', 'parse_int'),
        'msg-param-sub-plan': ('subscription_type', 'parse_subscription_type'),

        'msg-param-sub-plan-name': 'subscription_plan_name',

        'msg-param-ritual-name': 'ritual_name',

        'msg-param-threshold': 'bits_badge_tier',

        # (Commands)
        # HOSTTARGET
        'number-of-viewers': 'number_of_viewers'
    }

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

    # msg-id's
    _MESSAGE_GROUP_REMAPPINGS = {
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
        'other': {
            'cmds_available': 'cmds_available',
            'unrecognized_cmd': 'unrecognized_cmd',
            'no_permission': 'no_permission',
            'msg_ratelimit': 'rate_limit_reached_message',
        }

    }
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
        'other': [
            'clear_chat',
            'reconnect'
        ]
    }

    _MESSAGE_TYPE_REMAPPING = {}
    for message_group in _MESSAGE_GROUP_REMAPPINGS:
        value = _MESSAGE_GROUP_REMAPPINGS[message_group]
        _MESSAGE_TYPE_REMAPPING.update(value)

        if message_group not in _MESSAGE_GROUPS:
            _MESSAGE_GROUPS[message_group] = []
        _MESSAGE_GROUPS[message_group] += list(value.values())

    # print(_MESSAGE_TYPE_REMAPPING)

    @staticmethod
    def _parse_irc_item(match, params={}):  # self, , params
        info = {}

        split_info = match.group(1).split(';')

        # print(split_info)
        for item in split_info:
            keys = item.split('=', 1)
            if(len(keys) != 2):
                print('ERROR', keys, item, match.groups())  # TODO debug
                continue
            # print(keys[0],keys[1])

            ChatDownloader.remap(info, TwitchChatDownloader._IRC_REMAPPING,
                                 TwitchChatDownloader._REMAP_FUNCTIONS, keys[0], keys[1])

        message_match = match.group(3)
        if(message_match):
            info['message'] = message_match

        badge_metadata = info.pop('author_badge_metadata', [])
        badge_info = info.get('author_badges', [])

        # print(badge_metadata,badge_info)

        subscriber_badge = next(
            (x for x in badge_info if x.get('type') == 'subscriber'), None)
        subscriber_badge_metadata = next(
            (x for x in badge_metadata if x.get('type') == 'subscriber'), None)
        if subscriber_badge and subscriber_badge_metadata:
            months = subscriber_badge_metadata['version']
            subscriber_badge['months'] = months
            subscriber_badge['title'] = subscriber_badge['description'] = '{}-Month Subscriber'.format(
                months)

        if(info.get('author_badges') == []):  # remove if empty
            info.pop('author_badges')
        # for i in range(len(badge_info)):
        #     #print(badge_info, badge_info[i])
        #     #if(i < len(badge_metadata)):
        #     # Only used for subscriber months currently
        #     if(badge_info[i].get('name') == 'subscriber'):

        #     else:
        #         pass

            # overwrite data if remapping specified
            # remap = TwitchChatDownloader._BADGE_NAME_REMAPPING.get(
            #     badge_info[i]['badge'])
            # if(remap): # must use remapping function
            #     if(callable(remap)):
            #         badge_info[i]['name'] = remap(badge_info[i])
            #     elif(remap):
            #         badge_info[i]['name'] = remap
            #     else:
            #         # TODO debug
            #         if(params.get('logging') in ('debug', 'errors_only')):
            #             debug_print('Unknown badge: {}'.format(badge_info[i]))
            #             debug_print(info)
            #             print()

            #print(badge_info[i], 'remap', remap)

        author_display_name = info.get('author_display_name')
        if(author_display_name):
            info['author_name'] = author_display_name.lower()

        original_action_type = match.group(2)

        if(original_action_type):
            new_action_type = TwitchChatDownloader._ACTION_TYPE_REMAPPING.get(
                original_action_type)
            if(new_action_type):
                info['action_type'] = new_action_type
            else:
                # unknown action type
                info['action_type'] = original_action_type

        #message_type_info = [original_action_type, ]

        original_message_type = info.get('message_type')
        if(original_message_type):
            new_message_type = TwitchChatDownloader._MESSAGE_TYPE_REMAPPING.get(
                original_message_type)
            if(new_message_type):
                info['message_type'] = new_message_type
            else:
                print('DEBUG |', 'unknown message type:', original_message_type)
                #info['message_type'] = 'unknown'
        else:
            info['message_type'] = info['action_type']  # 'normal_'+

        if(original_action_type == 'CLEARCHAT'):
            if(message_match):  # is a ban
                info['message_type'] = 'ban_user'
                info['ban_type'] = 'timeout' if info.get(
                    'ban_duration') else 'permanent'
                info['banned_user'] = info.pop('message', '')

            else:  # did /clearchat
                pass

        follower_only = info.get('follower_only')
        if(follower_only):
            info['follower_only'] = follower_only != -1
            if(follower_only > 0):
                info['minutes_to_follow_before_chatting'] = follower_only

        slow_mode = info.get('slow_mode')
        if(slow_mode is not None):
            if slow_mode != 0:
                info['slow_mode'] = True
                info['seconds_to_wait'] = slow_mode
            else:
                info['slow_mode'] = False

        #print(info, flush=True)
    # _MESSAGE_TYPES = {
    #     'PRIVMSG': 'text_message',
    #     'USERNOTICE': '?',  # used for sub messages and hellos
    #     'CLEARCHAT': '?'  # used for timeouts/bans,

    #     #'CLEARMSG' - message_deleted

    #     # Purges all chat messages in a channel, or purges chat messages from a specific user, typically after a timeout or ban.

    # }
        # # print(match.groups())

        return info

    temp = []

    def get_chat_by_stream_id(self, stream_id, params):
        print('get_chat_by_stream_id:', stream_id)

        twitch_chat_irc = TwitchChatIRC()

        max_attempts = self.get_param_value(params, 'max_attempts')
        max_messages = self.get_param_value(params, 'max_messages')
        message_list = self.get_param_value(params, 'messages')
        callback = self.get_param_value(params, 'callback')
        message_receive_timeout = self.get_param_value(
            params, 'message_receive_timeout')
        timeout = self.get_param_value(params, 'timeout')

        buffer_size = self.get_param_value(params, 'buffer_size')
        # if(params.get('logging') != 'none'):
        #     print('Getting chat for', initial_title_info)

        # max_attempts = self.get_param_value(params, 'max_attempts')
        # max_messages = self.get_param_value(params, 'max_messages')
        # message_list = self.get_param_value(params, 'messages')
        #callback = self.get_param_value(params, 'callback')

        messages_groups_to_add = self.get_param_value(
            params, 'message_groups') or []
        messages_types_to_add = self.get_param_value(
            params, 'message_types') or []

        #print(messages_groups_to_add, messages_types_to_add, flush=True)

        twitch_chat_irc.set_timeout(message_receive_timeout)
        twitch_chat_irc.join_channel(stream_id)

        # if(on_message is None):
        #     on_message = self.__print_message

        print('Begin retrieving messages:')

        time_since_last_message = 0
        readbuffer = ''

        while True:
            try:
                new_info = twitch_chat_irc.recvall(buffer_size)

                # print('new_info',new_info)
                readbuffer += new_info
                q = readbuffer
                # print(readbuffer)
                # print('==========', )
                # continue

                if('PING :tmi.twitch.tv' in readbuffer):
                    twitch_chat_irc.send_raw('PONG :tmi.twitch.tv')
                    # print('pong')

                matches = list(self._MESSAGE_REGEX.finditer(readbuffer))
                # print(readbuffer)

                #print(buffer_size, len(readbuffer))
                # print(matches)
                if(matches):
                    time_since_last_message = 0

                    # sometimes a buffer does not contain a full message
                    if(not readbuffer.endswith('\r\n')):  # last one is incomplete
                        #matches = matches[:-1]

                        last_index = matches[-1].span()[1]
                        # pass remaining information to next attempt
                        readbuffer = readbuffer[last_index:]

                    else:
                        # the whole readbuffer was read correctly.
                        # clear readbuffer
                        readbuffer = ''

                    for match in matches:

                        data = self._parse_irc_item(match, params)

                        # if(params.get('logging') == 'normal'):
                        #     pass

                        if('all' in messages_groups_to_add):
                            pass

                        else:
                            # check whether to skip this message or not, based on its type

                            valid_message_types = []
                            for message_group in messages_groups_to_add or []:
                                # print(message_group)
                                valid_message_types += self._MESSAGE_GROUPS.get(
                                    message_group, [])

                            for message_type in messages_types_to_add or []:
                                valid_message_types.append(message_type)

                            # print(data.get('message_type'),
                            #       valid_message_types)
                            if(data.get('message_type') not in valid_message_types):
                                continue

                        message_list.append(data)
                        self.perform_callback(callback, data)

                        if(max_messages is not None and len(message_list) >= max_messages):
                            return message_list

            except socket.timeout:
                # print('time_since_last_message',time_since_last_message)
                if(timeout != None):
                    time_since_last_message += message_receive_timeout

                    if(time_since_last_message >= timeout):
                        print('No data received in', timeout,
                              'seconds. Timing out.')
                        break

        # create new socket
        # twitch_socket = socket.socket()

        # # start connection
        # twitch_socket.connect((self._HOST, self._PORT))
        # # print('Connected to',self._HOST,'on port',self._PORT)

        # # log in
        # self.send_raw(twitch_socket, 'CAP REQ :twitch.tv/tags')
        #  self.send_raw(twitch_socket, 'PASS ' + self._PASS)
        #   self.send_raw(twitch_socket, 'NICK ' + self._NICK)

    def get_chat_messages(self, params):
        super().get_chat_messages(params)

        url = self.get_param_value(params, 'url')

        for regex, function_name in self._REGEX_FUNCTION_MAP:
            match = re.search(regex, url)
            if(match):
                return getattr(self, function_name)(match.group('id'), params)

        # if(match):
        #     match.group('id')
        #     return self.get_chat_by_video_id(match.group('id'), params)

            # if(match.group('id')):  # normal youtube video
            #     return

            # else:  # TODO add profile, etc.
            #     pass

    # def get_chat_messages(self, url):
    #     pass

    # # e.g. 'https://www.twitch.tv/spamfish/videos?filter=all'
    # _VALID_VIDEOS_URL = r'https?://(?:(?:www|go|m)\.)?twitch\.tv/(?P<id>[^/]+)/(?:videos|profile)'

    # # e.g. 'https://www.twitch.tv/vanillatv/clips?filter=clips&range=all'
    # _VALID_VIDEO_CLIPS_URL = r'https?://(?:(?:www|go|m)\.)?twitch\.tv/(?P<id>[^/]+)/(?:clips|videos/*?\?.*?\bfilter=clips)'

    # # e.g. 'https://www.twitch.tv/collections/wlDCoH0zEBZZbQ'
    # _VALID_COLLECTIONS_URL = r'https?://(?:(?:www|go|m)\.)?twitch\.tv/collections/(?P<id>[^/]+)'
