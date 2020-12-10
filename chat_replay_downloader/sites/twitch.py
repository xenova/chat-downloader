import re
import json
import time
import socket

from .common import ChatDownloader

from ..errors import TwitchError, CallbackFunction

from ..utils import (
    ensure_seconds,
    timestamp_to_microseconds,
    seconds_to_time,
    try_get,
    int_or_none,
    replace_with_underscores
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
    def __init__(self, updated_init_params={}):
        super().__init__(updated_init_params)
        # self._name = None
        # self.name = 'Twitch.tv'

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

    _REMAP_FUNCTIONS = {
        'parse_timestamp': timestamp_to_microseconds,
        'get_body': lambda x: x.get('body'),
        'parse_author_images': lambda x: TwitchChatDownloader.parse_author_images(x),

        'parse_badges': lambda x: TwitchChatDownloader.parse_badges(x),

        'parse_int': int_or_none,

        'replace_with_underscores': replace_with_underscores

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
    def create_author_image(url, width, height):
        return {
            'url': url,
            'width': width,
            'height': height
        }

    @staticmethod
    def parse_author_images(original_url):
        smaller_icon = original_url.replace('300x300', '70x70')
        return [
            TwitchChatDownloader.create_author_image(original_url, 300, 300),
            TwitchChatDownloader.create_author_image(smaller_icon, 70, 70),
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
            info.update(TwitchChatDownloader._parse_item(author_info))

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

        api_url = self._API_TEMPLATE.format(vod_id, self._CLIENT_ID)

        # api calls start here
        content_offset_seconds = (start_time or 0) + offset

        cursor = ''
        while True:
            url = '{}&cursor={}&content_offset_seconds={}'.format(
                api_url, cursor, content_offset_seconds)

            # TODO use max attempts
            info = self._session_get_json(url)

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

                message_list.append(data)
                print(data.get('time_text'), data.get('message'))

                if(callback is None):
                    pass
                    # print
                    # self.print_item(data)

                elif(callable(callback)):
                    self.perform_callback(callback)

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
        r'^@(.+?(?=\s+:))(?:\s\S*?)tmi\.twitch\.tv\s(\S+)[^:\r\n]*:+([^\r\n]*)', re.MULTILINE)

    # e.g. # @emote-only=0;followers-only=10;r9k=0;rituals=0;room-id=86061418;slow=10;subs-only=0 :tmi.twitch.tv ROOMSTATE #5uppp
    # @ban-duration=1;room-id=223191589;target-user-id=596619271;tmi-sent-ts=1607456802152 :tmi.twitch.tv CLEARCHAT #tubbo :sammydg11111
    # _ROOM_STATE_REGEX = ''

    # @badge-info=;badges=;color=;display-name=mindteam2003;emotes=81274:0-5;flags=;id=fcb792fd-9137-4dd0-8cc8-6c1a2cf2fa7f;login=mindteam2003;mod=0;msg-id=ritual;msg-param-ritual-name=new_chatter;room-id=116228390;subscriber=0;system-msg=@mindteam2003\sis\snew\shere.\sSay\shello!;tmi-sent-ts=1607458140070;user-id=618090603;user-type= :tmi.twitch.tv USERNOTICE #tommyinnit :VoHiYo

    _EMOTE_URL_TEMPLATE = 'http://static-cdn.jtvnw.net/emoticons/v1/:<emote ID>/:<size>'
    _MESSAGE_TYPES = {
        'PRIVMSG': 'text_message',
        'USERNOTICE': '?',  # used for sub messages and hellos
        'CLEARCHAT': '?'  # used for timeouts/bans,

        #'CLEARMSG' - message_deleted


        # Purges all chat messages in a channel, or purges chat messages from a specific user, typically after a timeout or ban.



    }

    @staticmethod
    def parse_badges(badge_info):
        #print('badge_info "{}"'.format (badge_info), badge_info.split(','))
        info = []
        if(not badge_info):
            return info

        for badge in badge_info.split(','):
            split = badge.split('/')
            info.append({
                'badge': replace_with_underscores(split[0]),
                'version': int_or_none(split[1], split[1])
            })
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

        'emote-sets': 'emote_sets',  #TODO split by,?


        # message	The message.

        # GENERAL
        'color': 'colour',  # TODO make same as YT?
        'display-name': 'author_display_name',
        'user-id': 'author_id',
        'message': 'message', # The message.



        # PRIVMSG
        'badge-info': ('badge_metadata', 'parse_badges'),
        'badges': ('badge_info', 'parse_badges'),



        'bits': ('bits', 'parse_int'),

        # TODO change formatting to:
        # 'id': 'message_id'

        'id': 'message_id',
        # 'mod': ('is_moderator', 'do_nothing'), #already included in badges
        'room-id': 'channel_id',

        'tmi-sent-ts': ('timestamp', 'parse_int'),


        # ROOMSTATE
        'emote-only': ('emote_only_mode', 'parse_int'),
        'followers-only': ('follower_only_mode', 'parse_int'),
        'r9k': ('r9k_mode', 'parse_int'),
        'slow': ('slow_mode', 'parse_int'),
        'subs-only': ('subscriber_only_mode', 'parse_int'),

        # USERNOTICE
        'msg-id': 'message_type',

        'system-msg': 'system_message',

        # USERNOTICE - other
        # 'msg-param-cumulative-months':

    }

    # @badge-info=<badge-info>;badges=<badges>;color=<color>;
    # display-name=<display-name>;emotes=<emotes>;
    # id=<id-of-msg>;mod=<mod>;room-id=<room-id>;
    # subscriber=<subscriber>;tmi-sent-ts=<timestamp>;
    # turbo=<turbo>;user-id=<user-id>;user-type=<user-type>
    # :<user>!<user>@<user>.tmi.twitch.tv PRIVMSG #<channel> :<message>

    @staticmethod
    def _parse_irc_item(match):  # self, , params
        info = {}

        split_info = match.group(1).split(';')

        # print(split_info)
        for item in split_info:
            keys = item.split('=', 1)
            # print(keys[0],keys[1])

            ChatDownloader.remap(info, TwitchChatDownloader._IRC_REMAPPING,
                                 TwitchChatDownloader._REMAP_FUNCTIONS, keys[0], keys[1])
            # remap(info, remapping_dict, remapping_functions, remap_key, remap_value):
            # remap = .get()

            # if(remap):
            #     if(isinstance(remap, tuple)):
            #         index, mapping_function = remap
            #         [index] = [mapping_function](
            #             keys[1])
            #     else:
            #         info[remap] = keys[1]

            # pass
            # TwitchChatDownloader.

        badge_metadata = info.pop('badge_metadata', [])

        for i in range(len(badge_metadata)):
            if(badge_metadata[i]['badge'] == 'subscriber'):
                badge_info = info.get('badge_info', [])
                badge_info[i]['months'] = badge_metadata[i]['version']
                break

        author_display_name = info.get('author_display_name')
        if(author_display_name):
            info['author_name'] = author_display_name.lower()

        # for badge in :
        #     if(badge['badge']):
        #         info['badge_info']
        #         break
        # author_badges
            # for key in item:
        #     original_info = item[key]
        #
        #     if(remap):
        #         index, mapping_function = remap
        #         info[index] = TwitchChatDownloader._REMAP_FUNCTIONS[mapping_function](
        #             original_info)
        #     info[keys[0]] = info[1]

        # TODO use remapping for match.group(2)
        # PRIVMSG --> text_message sometimes
        original_message_type = match.group(2).lower()

        ban_duration = info.get('ban_duration')
        if(original_message_type == 'clearchat'):  # TODO to change this
            if(ban_duration):
                info['ban_type'] = 'timeout'
            else:  # no ban duration
                info['ban_type'] = 'permanent'

            # info['ban_type']
            pass

        message_type_info = [original_message_type, info.get('message_type')]

        info['message_type'] = '_'.join(filter(lambda x: x, message_type_info))
        # highlighted-message_privmsg

        # if(message_type_info):
        #     info['message_type'] += '_'

        # info['message_type'] +=   # .lower()
        info['message'] = match.group(3)

        # # print(match.groups())

        return info

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

                        data = self._parse_irc_item(match)

                        if(data.get('message_type') != 'privmsg'):

                            print(q)
                            print(data)

                        # print(data)
                        # if('bits' in data):
                        #     print(match.groups())
                        #     print(data)

                        # continue

                        message_list.append(data)
                        if(not callback):
                            pass
                            # print(data.get('timestamp'),data.get('message'))

                        elif(callable(callback)):
                            self.perform_callback(callback)

                        # if(callable(on_message)):
                        #     try:
                        #         on_message(data)
                        #     except TypeError:
                        #         raise Exception(
                        #             'Incorrect number of parameters for function '+on_message.__name__)

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
