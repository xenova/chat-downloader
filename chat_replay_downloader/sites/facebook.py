import json
from urllib import parse
import xml.etree.ElementTree as ET
import isodate
import time

#import requests
import re

from .common import ChatDownloader

from ..utils import (
    remove_prefixes,
    multi_get,
    try_get_first_key,
    safe_convert_text,
    try_get,
    seconds_to_time,
    camel_case_split
)


class FacebookChatDownloader(ChatDownloader):
    _FB_HOMEPAGE = 'https://www.facebook.com'
    _FB_HEADERS = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': _FB_HOMEPAGE,
        'Accept-Language': 'en-US,en;',  # q=0.9
    }

    # _INITIAL_URL_TEMPLATE = 'https://www.facebook.com/video.php?v={}'  # &fref=n
    _INITIAL_DATR_REGEX = r'_js_datr\",\"([^\"]+)'
    _INITIAL_LSD_REGEX = r'<input.*?name=\"lsd\".*?value=\"([^\"]+)[^>]*>'

    def __init__(self, updated_init_params={}):
        super().__init__(updated_init_params)

        # Get cookie data:
        # TODO only update if `cookies` not in new init params

        # init_url = self._INITIAL_URL_TEMPLATE.format(vod_id)
        # init_url = 'https://www.facebook.com/disguisedtoast/videos/382024729792892'

        #jar = requests.cookies.RequestsCookieJar()

        # update headers for all subsequent FB requests
        self.update_session_headers(self._FB_HEADERS)

        #print('before', self.get_cookies_dict(), flush=True)

        # TODO , timeout=timeout_duration (from init params)
        timeout_duration = 10
        # used to get cookies
        initial_data = self._session_get(
            self._FB_HOMEPAGE, timeout=timeout_duration,
            headers=self._FB_HEADERS, allow_redirects=False).text
        #print('after', self.get_cookies_dict(), flush=True)

        datr = re.search(self._INITIAL_DATR_REGEX, initial_data)
        if datr:
            datr = datr.group(1)
        else:
            print('unable to get datr cookie')
            raise Exception  # TODO

        sb = self.get_cookie_value('sb')
        fr = self.get_cookie_value('fr')

        # print('sb:', sb, flush=True)
        # print('fr:', fr, flush=True)
        # print('datr:', datr, flush=True)

        lsd_info = re.search(self._INITIAL_LSD_REGEX, initial_data)
        if not lsd_info:
            print('no lsd info', flush=True)
            raise Exception  # TODO

        lsd = lsd_info.group(1)
        # print('lsd:', lsd, flush=True)

        request_headers = {
            # TODO sb and fr unnecessary?
            # wd=1122x969;
            'Cookie': 'sb={}; fr={}; datr={};'.format(sb, fr, datr)
        }
        self.update_session_headers(request_headers)

        self.data = {
            # TODO need things like jazoest? (and other stuff from hidden elements/html)
            '__a': 1,  # TODO needed?
            'lsd': lsd,
        }

    def __str__(self):
        return 'facebook.com'

    # Regex provided by youtube-dl
    _VALID_URL = r'''(?x)
            (?:
                https?://
                    (?:[\w-]+\.)?(?:facebook\.com)/
                    (?:[^#]*?\#!/)?
                    (?:[^/]+/videos/(?:[^/]+/)?)
            )
            (?P<id>[0-9]+)
            '''

    _TESTS = [

    ]

    _VIDEO_PAGE_TAHOE_TEMPLATE = 'https://www.facebook.com/video/tahoe/async/{}/?chain=true&isvideo=true&payloadtype=primary'
    _STRIP_TEXT = 'for (;;);'

    def parse_fb_json(self, response):
        return json.loads(remove_prefixes(response.text, self._STRIP_TEXT))

    _VOD_COMMENTS_API = 'https://www.facebook.com/videos/vodcomments/'
    _GRAPH_API = 'https://www.facebook.com/api/graphql/'

    def get_initial_info(self, video_id, params):

        response = self._session_post(self._VIDEO_PAGE_TAHOE_TEMPLATE.format(
            video_id), headers=self._FB_HEADERS, data=self.data)

        json_data = self.parse_fb_json(response)

        instances = multi_get(json_data, 'jsmods', 'instances')

        video_data = {}
        for item in instances:
            if try_get(item, lambda x: x[1][0]) == 'VideoConfig':
                video_item = item[2][0]
                if video_item.get('video_id'):
                    video_data = video_item['videoData'][0]
                    break
        # print(video_data)
        if not video_data:
            print('unable to get video data')
            raise Exception

        dash_manifest = video_data.pop('dash_manifest', None)

        if dash_manifest:  # when not live, this returns
            dash_manifest_xml = ET.fromstring(dash_manifest)
            video_data['duration'] = isodate.parse_duration(
                dash_manifest_xml.attrib['mediaPresentationDuration']).total_seconds()

        return video_data

    @staticmethod
    def _parse_feedback(feedback):
        new_feedback = {}
        edges = multi_get('top_reactions', 'edges')
        if not edges:
            return new_feedback

        new_feedback['reaction_types'] = []

        for edge in edges:
            node = edge.get('node')
            reaction_item = {
                'key': node.get('key'),
                'id': node.get('id'),
                'name': node.get('reaction_type'),
                'count': edge.get('reaction_count')
            }

            new_feedback['reaction_types'].append(reaction_item)

        new_feedback['count'] = multi_get(feedback, 'reactors', 'count')
        new_feedback['count_reduced'] = multi_get(
            feedback, 'reactors', 'count_reduced')

        return new_feedback

    # _AUTHOR_REMAP
    # @staticmethod
    # def parse_author(feedback):
    #     pass

    # 'StoryAttachmentTipJarPaymentStyleRenderer'

    @staticmethod
    def _parse_attachment_styles(item):
        parsed = {}
        item_info = None

        for t in ('media', 'target'): # In order of precedence
            item_info = multi_get(item, 'style_type_renderer', 'attachment', t)
            if item_info:
                print("GOT IT: ", item_info)
                break # found something to parse

        if not item_info:
            print('UNKNOWN TARGET')
            print(item)
            return parsed

        original_target_type = item_info.get('__typename')
        parsed['type'] = camel_case_split(original_target_type)
        parsed['id'] = item_info.get('id')

        if original_target_type == 'VideoTipJarPayment':

            parsed['icon'] = item_info.get('stars_image_on_star_quantity')
            parsed['quantity'] = item_info.get('spark_quantity')
            parsed['text'] = 'Sent {} Star{}'.format(
                parsed['quantity'], 's' if parsed['quantity'] != 1 else '')
        elif original_target_type == 'Sticker':
            parsed['label'] = item_info.get('label')
            image = item_info.get('image')
            if image:
                parsed['image'] = ChatDownloader.create_image(
                    image.get('uri'),image.get('width'),image.get('height'),
                )

        elif original_target_type == 'Photo':
            print('IMAGE')
            image = item_info.get('image') or item_info.get('fallback_image')
            print(image)
            if image:
                parsed['image'] = ChatDownloader.create_image(
                    image.get('uri'),image.get('width'),image.get('height'),
                )

        elif original_target_type == 'Other...':
            pass
        else:
            print('UNKNOWN ATTACHMENT:', original_target_type)
            print(item)

        return parsed

    @staticmethod
    def _parse_author_badges(item):

        keys = (('badge_asset', 'small'), ('information_asset', 'colour'))
        icons = list(map(lambda x: ChatDownloader.create_image(
            FacebookChatDownloader._FB_HOMEPAGE+item.get(x[0]), 24, 24, x[1]), keys))
        icons.append(ChatDownloader.create_image(
            item.get('multiple_badge_asset'), 36, 36, 'large'))

        return {
            'title': item.get('text'),
            'alternative_title': item.get('information_title'),
            'description': item.get('information_description'),
            'icons': icons,

            # badge_asset
            # multiple_badge_asset
            # information_asset

            'type': item.get('identity_badge_type')

            # 'information_asset', 'text'

        }

    _REMAP_FUNCTIONS = {
        'test': lambda x: x.get('test'),
        'parse_feedback': lambda x: FacebookChatDownloader._parse_feedback(x),
        'multiply_by_million': lambda x: x*1000000,
        'parse_edit_history': lambda x: x.get('count'),

        'parse_item': lambda x: FacebookChatDownloader._parse_live_stream_node(x),

        'get_source_dialect_name': lambda x: x.get('source_dialect_name'),
        'get_body_text': lambda x: x.get('text') if x else None,

        'parse_author_badges': lambda x: list(map(FacebookChatDownloader._parse_author_badges, x)),

        'parse_attachment_styles': lambda x: list(map(FacebookChatDownloader._parse_attachment_styles, x)),

        'to_lowercase': lambda x: x.lower()
    }

    # _MESSAGE_TYPES = {
    #     'Comment'
    # }

    _REMAPPING = {
        'id': 'message_id',
        'community_moderation_state': 'community_moderation_state',

        # attachments

        'author': 'author',


        'feedback': ('reactions', 'parse_feedback'),
        'created_time': ('timestamp', 'multiply_by_million'),


        'upvote_downvote_total': 'upvote_downvote_total',
        'is_author_banned_by_content_owner': 'is_author_banned',
        'is_author_original_poster': 'is_author_original_poster',
        'is_author_bot': 'is_author_bot',
        'is_author_non_coworker': 'is_author_non_coworker',
        # if banned, ban_action?

        'comment_parent': 'comment_parent',

        'edit_history': ('number_of_edits', 'parse_edit_history'),


        'timestamp_in_video': 'time_in_seconds',
        'written_while_video_was_live': 'written_while_video_was_live',



        'translatability_for_viewer': ('message_dialect', 'get_source_dialect_name'),


        'url': 'message_url',

        'body': ('message', 'get_body_text'),

        'identity_badges_web': ('author_badges', 'parse_author_badges'),

        'attachments': ('attachments', 'parse_attachment_styles')

        # 'comment_parent':('in_reply_to','parse_item')
    }

    _AUTHOR_REMAPPING = {
        'id': 'id',
        'name': 'name',
        '__typename': 'type',
        'url': 'url',

        'is_verified': 'is_verified',

        'gender': ('gender', 'to_lowercase'),  # TODO lowercase?
        'short_name': 'short_name'
    }

    @ staticmethod
    def _parse_live_stream_node(node, info={}):
        for key in node:
            ChatDownloader.remap(info, FacebookChatDownloader._REMAPPING,
                                 FacebookChatDownloader._REMAP_FUNCTIONS, key, node[key])

        author_info = info.pop('author', None)
        #info['author'] = {}
        if author_info:
            ChatDownloader.create_author_info(info, 'is_author_banned', 'is_author_banned',
                                              'is_author_original_poster', 'is_author_bot', 'is_author_non_coworker', 'author_badges')

            for key in author_info:
                ChatDownloader.remap(info['author'], FacebookChatDownloader._AUTHOR_REMAPPING,
                                     FacebookChatDownloader._REMAP_FUNCTIONS, key, author_info[key])

            if 'profile_picture_depth_0' in author_info:
                info['author']['images'] = []
                for size in ((0, 32), (1, 24)):
                    url = multi_get(
                        author_info, 'profile_picture_depth_{}'.format(size[0]), 'uri')
                    info['author']['images'].append(
                        ChatDownloader.create_image(url, size[1], size[1]))

        # author_badges = info.pop('author_badges', None)
        # if author_badges:
        #     info['author']['badges'] = author_badges

        in_reply_to = info.pop('comment_parent', None)
        if isinstance(in_reply_to, dict) and in_reply_to:
            info['in_reply_to'] = FacebookChatDownloader._parse_live_stream_node(
                in_reply_to, {})

        time_in_seconds = info.get('time_in_seconds')
        if time_in_seconds is not None:
            info['time_text'] = seconds_to_time(time_in_seconds)

        message = info.get('message')
        if message:
            info['message'] = message
            info['message_type'] = 'text_message'
        else:
            info.pop('message', None)  # remove if empty

        # remove the following if empty:
        if info.get('reactions') == {}:  # no reactions
            info.pop('reactions')

        if info.get('attachments') == []:
            info.pop('attachments')
            # print("AAAAAAAA")
            # print(info.get('attachments'), node)

        return info

    def get_live_chat_by_video_id(self, video_id, initial_info, params):
        print('live')

        message_list = self.get_param_value(params, 'messages')
        callback = self.get_param_value(params, 'callback')

        buffer_size = 25  # max num comments returned by api call
        cursor = ''
        variables = {
            'videoID': video_id,

        }
        data = {
            'variables': json.dumps(variables),
            'doc_id': '4889623951078943',  # specifies what API call this is?
            # 'cursor' : cursor
            # &first=12&after=<end_cursor>
        }
        data.update(self.data)
        #p = (), params=p
        last_ids = []
        while True:
            response = self._session_post(
                self._GRAPH_API, headers=self._FB_HEADERS, data=data).json()
            # print(response)
            # return
            feedback = multi_get(response, 'data', 'video', 'feedback') or {}
            if not feedback:
                print('no feedback')  # TODO debug
                continue

            top_level_comments = multi_get(
                response, 'data', 'video', 'feedback', 'top_level_comments')
            edges = top_level_comments.get('edges')[::-1]  # reverse order

            # TODO - get pagination working
            # page_info = top_level_comments.get('page_info')
            # after = page_info.get('end_cursor')

            for edge in edges:
                node = edge.get('node')
                if not node:
                    # TODO debug
                    print('no node found in edge')
                    print(edge)
                    continue
                comment_id = node.get('id')

                # remove items that have already been parsed
                if comment_id in last_ids:
                    print('=', end='', flush=True)
                    continue
                last_ids.append(comment_id)

                last_ids = last_ids[-buffer_size:]  # force x items

                if not node:
                    # TODO debug
                    print('no node', edge)
                    continue

                parsed_node = FacebookChatDownloader._parse_live_stream_node(
                    node)
                message_list.append(parsed_node)
                print(parsed_node)
                # if(max_messages is not None and len(message_list) >= max_messages):
                #     return message_list  # if max_messages specified, return once limit has been reached

                self.perform_callback(callback, parsed_node)
                # print(parsed_node)

            print('got', len(edges), 'message', flush=True)

            if not top_level_comments:
                print('err2')
                print(response)

    def get_chat_replay_by_video_id(self, video_id, initial_info, params):
        print('vod')

        message_list = self.get_param_value(params, 'messages')
        callback = self.get_param_value(params, 'callback')
        max_duration = initial_info.get('duration', float('inf'))

        # useful tool (convert curl to python request)
        # https://curl.trillworks.com/
        timeout_duration = 10  # TODO make this modifiable

        initial_request_params = (
            ('eft_id', video_id),
            ('target_ufi_instance_id', 'u_2_1'),
            # ('should_backfill', 'false'), # used when seeking? - # TODO true on first try?
        )

        time_increment = 60  # Facebook gets messages by the minute
        # TODO make this modifiable

        start_time = self.get_param_value(params, 'start_time') or 0
        end_time = self.get_param_value(params, 'end_time') or float('inf')

        next_start_time = max(start_time, 0)
        end_time = min(end_time, max_duration)

        #print(next_start_time, end_time, type(next_start_time), type(end_time))
        # return
        #total = []
        while True:
            next_end_time = min(next_start_time + time_increment, end_time)
            times = (('start_time', next_start_time),
                     ('end_time', next_end_time))

            # print(times, flush=True)

            request_params = initial_request_params + times

            response = self._session_post(self._VOD_COMMENTS_API, headers=self._FB_HEADERS,
                                          params=request_params, data=self.data, timeout=timeout_duration)
            json_data = self.parse_fb_json(response)
            # print(json_data)

            payloads = multi_get(json_data, 'payload', 'ufipayloads')
            if not payloads:
                pass
                # TODO debug
                #print('no comments between',next_start_time, next_end_time, flush=True)
                # print('err1')
                # print(json_data)

            next_start_time = next_end_time

            if next_start_time >= end_time:
                print('end')
                return message_list

            for payload in payloads:
                time_offset = payload.get('timeoffset')
                # print(test)

                ufipayload = payload.get('ufipayload')
                if not ufipayload:
                    print('no ufipayload', payload)
                    continue

                # ['comments'][0]['body']['text']
                comments = ufipayload.get('comments')
                pinned_comments = ufipayload.get('pinnedcomments')
                profile = try_get_first_key(ufipayload.get('profiles'))

                text = safe_convert_text(comments[0]['body']['text'])
                print(time_offset, text)

                message_list.append(text)

                ChatDownloader.perform_callback(callback, payload)
                #total += comments

            #print('got', len(payloads), 'messages.','Total:', len(message_list))

    def get_chat_by_video_id(self, video_id, params):
        super().get_chat_messages(params)

        print('video_id:', video_id)

        initial_info = self.get_initial_info(video_id, params)

        start_time = self.get_param_value(params, 'start_time')
        end_time = self.get_param_value(params, 'end_time')

        # TODO if start or end time specified, use chat replay...
        # The tool works for both active and finished live streams.
        # if start/end time are specified, vods will be prioritised
        # if is live stream and no start/end time specified
        if initial_info.get('is_live_stream') and not start_time and not end_time:
            return self.get_live_chat_by_video_id(video_id, initial_info, params)
        else:
            return self.get_chat_replay_by_video_id(video_id, initial_info, params)

            # return
        # TODO try this
        # response = requests.post(
        #     'https://www.facebook.com/ajax/ufi/comment_fetch.php', data=data)
        # data = {
        #     'ft_ent_identifier': '382024729792892',
        #     # 'viewas': '',
        #     # 'source': '41',
        #     'offset': '14574',
        #     'length': '20',  # CONTROLS NUMBER OF ITEMS
        #     'orderingmode': 'recent_activity',
        # }

        # TODO live:
        # import requests

    def get_chat_messages(self, params):
        super().get_chat_messages(params)

        url = self.get_param_value(params, 'url')
        # messages = YouTubeChatDownloader.get_param_value(params, 'messages')

        match = re.search(self._VALID_URL, url)

        if(match):

            if(match.group('id')):  # normal youtube video
                return self.get_chat_by_video_id(match.group('id'), params)

            else:  # TODO add profile, etc.
                pass
