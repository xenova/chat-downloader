import re
import json
import time

from .common import ChatDownloader

from ..errors import TwitchError, CallbackFunction

from ..utils import (
    ensure_seconds,
    timestamp_to_microseconds,
    seconds_to_time,
    try_get
)

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
        'do_nothing': lambda x: x,
        'parse_timestamp': timestamp_to_microseconds,
        'get_body': lambda x: x.get('body'),
        'parse_author_images': lambda x : TwitchChatDownloader.parse_author_images(x)

    }

    _REMAPPING = {
        # 'origID' : ('mapped_id', 'remapping_function')
        '_id': ('id', 'do_nothing'),
        'created_at': ('timestamp', 'parse_timestamp'),
        'commenter': ('author_info','do_nothing'), # TODO pop later

        'content_offset_seconds': ('time_in_seconds', 'do_nothing'),




        'source':('source','do_nothing'),
        'state':('state','do_nothing'),
        'message':('message','get_body'), # TODO make sure body vs. fragments okay

        'name' : ('author_name', 'do_nothing'),
        'display_name' : ('author_display_name', 'do_nothing'),
        'logo': ('author_images', 'parse_author_images'),


        'type': ('author_type', 'do_nothing')


        #TODO 'type' # author type?
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
        #-70x70

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
    def _parse_item(item, offset = 0):
        info={}
        # info is starting point
        for key in item:
            original_info = item[key]
            remap = TwitchChatDownloader._REMAPPING.get(key)
            if(remap):
                index, mapping_function = remap
                info[index] = TwitchChatDownloader._REMAP_FUNCTIONS[mapping_function](
                    original_info)

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
    def get_chat_by_vod_id(self, vod_id, params, offset = 0, max_duration = None):
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

                if(before_start): # still getting to messages
                    continue
                elif(after_end): # after end
                    return message_list  # while actually searching, if time is invalid


                message_list.append(data)
                print(data.get('time_text'),data.get('message'))

                if(callback is None):
                    pass
                    #print
                    #self.print_item(data)

                elif(callable(callback)):
                    self.perform_callback(callback)

            cursor = info.get('_next')

            if not cursor: # no more
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

    def get_chat_by_stream_id(self, stream_id, params):
        print('get_chat_by_stream_id:', stream_id)
        pass

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
