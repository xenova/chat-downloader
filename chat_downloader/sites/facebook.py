from .common import (
    Chat,
    BaseChatDownloader,
    Remapper as r,
    Image
)
from ..utils.core import (
    remove_prefixes,
    multi_get,
    try_get_first_value,
    seconds_to_time,
    camel_case_split,
    ensure_seconds,
    attempts,
    get_title_of_webpage,
)

from ..debugging import log

import json
import re
import xml.etree.ElementTree as ET
import isodate
from json.decoder import JSONDecodeError
from requests.exceptions import RequestException


class FacebookChatDownloader(BaseChatDownloader):
    _FB_HOMEPAGE = 'https://www.facebook.com'
    _FB_HEADERS = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': _FB_HOMEPAGE,
        'Accept-Language': 'en-US,en;',
    }

    _INITIAL_DATR_REGEX = r'_js_datr\",\"([^\"]+)'
    _INITIAL_LSD_REGEX = r'<input.*?name=\"lsd\".*?value=\"([^\"]+)[^>]*>'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # update headers for all subsequent FB requests
        self.update_session_headers(self._FB_HEADERS)

        initial_data = self._session_get(
            self._FB_HOMEPAGE,
            headers=self._FB_HEADERS, allow_redirects=False).text

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
            print('no lsd info')
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

    _NAME = 'facebook.com'
    # Regex provided by youtube-dl

    _VALID_URLS = {
        '_get_chat_by_video_id': r'''(?x)
            (?:
                https?://
                    (?:[\w-]+\.)?(?:facebook\.com)/
                    (?:[^#]*?\#!/)?
                    (?:[^/]+/videos/(?:[^/]+/)?)
            )
            (?P<id>[0-9]+)
            '''
    }

    _TESTS = [

    ]

    _VIDEO_PAGE_TAHOE_TEMPLATE = _FB_HOMEPAGE + \
        '/video/tahoe/async/{}/?chain=true&isvideo=true&payloadtype=primary'

    def _parse_fb_json(self, response):
        text_to_parse = remove_prefixes(response.text, 'for (;;);')
        return json.loads(text_to_parse)

    _VOD_COMMENTS_API = _FB_HOMEPAGE + '/videos/vodcomments/'
    _GRAPH_API = _FB_HOMEPAGE + '/api/graphql/'
    _VIDEO_URL_FORMAT = _FB_HOMEPAGE + '/video.php?v={}'
    # _VIDEO_TITLE_REGEX = r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']\s*/>'

    def _attempt_fb_retrieve(self, url, max_attempts, retry_timeout, fb_json=False, **post_kwargs):
        for attempt_number in attempts(max_attempts):
            try:
                response = self._session_post(url, **post_kwargs)

                if fb_json:
                    return self._parse_fb_json(response)
                else:
                    return response.json()

            except JSONDecodeError as e:
                self.retry(attempt_number, max_attempts, e, retry_timeout,
                           text='Unable to parse JSON: `{}`'.format(response.text))

            except RequestException as e:
                self.retry(attempt_number, max_attempts, e, retry_timeout)

    def _get_initial_info(self, video_id, params):
        info = {}
        max_attempts = params.get('max_attempts')
        retry_timeout = params.get('retry_timeout')

        # TODO remove duplication - many similar methods
        json_data = self._attempt_fb_retrieve(
            self._VIDEO_PAGE_TAHOE_TEMPLATE.format(video_id),
            max_attempts,
            retry_timeout,
            True,
            headers=self._FB_HEADERS, data=self.data
        )
        # print(json_data)

        markup = multi_get(json_data, 'payload', 'video', 'markup', '__html')
        video_markup = ET.fromstring(markup)
        tags = [x.text for x in video_markup.findall(
            './/span[@class="_50f7"]')]
        if len(tags) >= 2:
            info['title'] = tags[0]
            info['username'] = tags[1]
        else:
            video_page_url = self._VIDEO_URL_FORMAT.format(video_id)
            for attempt_number in attempts(max_attempts):
                try:
                    html = self._session_get(video_page_url).text
                    match = get_title_of_webpage(html)
                    if match:
                        title_info = match.split(' - ', 1)
                        if len(title_info) == 2:
                            info['username'] = title_info[0]
                            info['title'] = title_info[1]
                    break
                except RequestException as e:
                    self.retry(attempt_number, max_attempts, e, retry_timeout)

        instances = multi_get(json_data, 'jsmods', 'instances')

        video_data = {}
        for item in instances:
            if multi_get(item, 1, 0) == 'VideoConfig':
                video_item = item[2][0]
                if video_item.get('video_id'):
                    video_data = video_item['videoData'][0]
                    # print(video_data)
                    break
        # print(video_data)
        if not video_data:
            print('unable to get video data')
            raise Exception

        dash_manifest = video_data.get('dash_manifest')

        if dash_manifest:  # when not live, this returns
            dash_manifest_xml = ET.fromstring(dash_manifest)
            info['duration'] = isodate.parse_duration(
                dash_manifest_xml.attrib['mediaPresentationDuration']).total_seconds()

        info['is_live'] = video_data['is_live_stream']
        return info

    @staticmethod
    def _parse_feedback(feedback):
        new_feedback = {}

        edges = multi_get(feedback, 'top_reactions', 'edges')

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

        new_feedback['total_count'] = multi_get(feedback, 'reactors', 'count')
        new_feedback['total_count_reduced'] = multi_get(
            feedback, 'reactors', 'count_reduced')

        return new_feedback

    @staticmethod
    def _get_text(item):
        return item.get('text') if item else None

    @staticmethod
    def _parse_image(item):
        return Image(item.get('uri'), item.get('width'), item.get('height')).json()

    @staticmethod
    def _get_uri(item):
        return item.get('uri')

    @staticmethod
    def _parse_attachment_info(original_item):
        item = {}

        if isinstance(original_item, (list, tuple)) and len(original_item) > 0:
            original_item = original_item[0]

        if not original_item:
            return item

        for key in original_item:
            r.remap(item, FacebookChatDownloader._TARGET_MEDIA_REMAPPING,
                    key, original_item[key])

        # VideoTipJarPayment
        quantity = item.get('quantity')
        if quantity:
            item['text'] = 'Sent {} Star{}'.format(
                quantity, 's' if quantity != 1 else '')

        # For photos:
        blurred_image = item.pop('blurred_image', None)
        massive_image = item.pop('massive_image', None)

        if blurred_image and massive_image:
            item['text'] = Image(blurred_image, massive_image.get(
                'width'), massive_image.get('height')).json()

        # style_infos
        donation_comment_text = item.pop('donation_comment_text', None)
        if donation_comment_text:
            entity = multi_get(donation_comment_text,
                               'ranges', 0, 'entity') or {}

            for key in entity:
                r.remap(
                    item, FacebookChatDownloader._TARGET_MEDIA_REMAPPING, key, entity[key])
            item['text'] = donation_comment_text.get('text')

        # DEBUGGING
        original_type_name = original_item.get('__typename')
        if original_type_name not in FacebookChatDownloader._KNOWN_ATTACHMENT_TYPES:
            print('debug')
            print('unknown attachment type:', original_type_name)
            print(original_item)
            print(item)
            input()

        return item

    @staticmethod
    def _parse_target(media):
        item = {}

        return item

    @staticmethod
    def _parse_author_badges(item):

        keys = (('badge_asset', 'small'), ('information_asset', 'colour'))
        icons = list(map(lambda x: Image(
            FacebookChatDownloader._FB_HOMEPAGE + item.get(x[0]), 24, 24, x[1]).json(), keys))

        icons.append(
            Image(item.get('multiple_badge_asset'), 36, 36, 'large').json())

        return {
            'title': item.get('text'),
            'alternative_title': item.get('information_title'),
            'description': item.get('information_description'),
            'icons': icons,

            # badge_asset
            # multiple_badge_asset
            # information_asset

            'icon_name': item.get('identity_badge_type')

        }

    _ATTACHMENT_REMAPPING = {
        'url': 'url',  # facebook redirect url,
        'source': r('source', _get_text),
        'title_with_entities': r('title', _get_text),

        'target': r('target', _parse_attachment_info),
        'media': r('media', _parse_attachment_info),
        'style_infos': r('style_infos', _parse_attachment_info),

        'attachment_text': r('text', _get_text),
    }

    _IGNORE_ATTACHMENT_KEYS = [
        'tracking',
        'action_links'
    ]

    _KNOWN_ATTACHMENT_KEYS = set(
        list(_ATTACHMENT_REMAPPING.keys()) + _IGNORE_ATTACHMENT_KEYS)

    @staticmethod
    def _parse_attachment_styles(item):
        parsed = {}
        attachment = multi_get(item, 'style_type_renderer', 'attachment')
        if not attachment:
            # TODO debug log
            print('NO ATTACHMENT')
            print(item)
            return parsed

        # set texts:
        for key in attachment:
            r.remap(parsed, FacebookChatDownloader._ATTACHMENT_REMAPPING,
                    key, attachment[key])

        for key in ('target', 'media', 'style_infos'):
            if parsed.get(key) == {}:
                parsed.pop(key)

        missing_keys = attachment.keys() - FacebookChatDownloader._KNOWN_ATTACHMENT_KEYS
        if missing_keys:
            print('MISSING ATTACHMENT KEYS:', missing_keys)
            print(item)
            print(parsed)
            input()

        return parsed

    _TARGET_MEDIA_REMAPPING = {
        'id': 'id',
        '__typename': r('type', camel_case_split),
        'fallback_image': r('image', _parse_image),
        'is_playable': 'is_playable',
        'url': 'url',

        'mobileUrl': 'mobile_url',


        # Sticker
        'pack': 'pack',
        'label': 'label',
        'image': r('image', _parse_image),

        # VideoTipJarPayment

        'stars_image_on_star_quantity': 'icon',
        'spark_quantity': 'quantity',



        # Page
        'name': 'name',
        'category_name': 'category',
        'address': 'address',
        'overall_star_rating': 'overall_star_rating',

        'profile_picture': r('profile_picture', _get_uri),

        # Photo
        'accessibility_caption': 'accessibility_caption',

        'blurred_image': r('blurred_image', _get_uri),
        'massive_image': 'massive_image',


        # FundraiserForStoryDonationAttachmentStyleInfo
        'donation_comment_text': 'donation_comment_text'

    }

    _KNOWN_ATTACHMENT_TYPES = [
        'Sticker',
        'VideoTipJarPayment',
        'Page',

        'Group',
        'ProfilePicAttachmentMedia',
        'User',
        'Photo',

        'ExternalUrl',
        'GenericAttachmentMedia',

        'ChatCommandResult',

        'CommentMessageInfo',
        'FundraiserForStoryDonationAttachmentStyleInfo'
    ]

    _REMAPPING = {
        'id': 'message_id',
        'community_moderation_state': 'community_moderation_state',

        # attachments

        'author': 'author',


        'feedback': r('reactions', _parse_feedback),
        'created_time': r('timestamp', lambda x: x * 1000000),


        'upvote_downvote_total': 'upvote_downvote_total',
        'is_author_banned_by_content_owner': 'is_author_banned',
        'is_author_original_poster': 'is_author_original_poster',
        'is_author_bot': 'is_author_bot',
        'is_author_non_coworker': 'is_author_non_coworker',
        # if banned, ban_action?

        'comment_parent': 'comment_parent',

        'edit_history': r('number_of_edits', lambda x: x.get('count')),


        'timestamp_in_video': 'time_in_seconds',
        'written_while_video_was_live': 'written_while_video_was_live',



        'translatability_for_viewer': r('message_dialect', lambda x: x.get('source_dialect_name')),


        'url': 'message_url',

        'body': r('message', _get_text),

        'identity_badges_web': r('author_badges', lambda x: list(map(FacebookChatDownloader._parse_author_badges, x))),

        'attachments': r('attachments', lambda x: list(map(FacebookChatDownloader._parse_attachment_styles, x)))

    }

    _AUTHOR_REMAPPING = {
        'id': 'id',
        'name': 'name',
        '__typename': r('type', camel_case_split),
        'url': 'url',

        'is_verified': 'is_verified',

        'gender': r('gender', lambda x: x.lower()),
        'short_name': 'short_name'
    }

    @ staticmethod
    def _parse_live_stream_node(node):
        # if info is None:
        #     info = {}
        info = {}

        for key in node:
            r.remap(info, FacebookChatDownloader._REMAPPING, key, node[key])

        author_info = info.pop('author', {})
        BaseChatDownloader._move_to_dict(
            info, 'author', create_when_empty=True)

        for key in author_info:
            r.remap(
                info['author'], FacebookChatDownloader._AUTHOR_REMAPPING, key, author_info[key])

        if 'profile_picture_depth_0' in author_info:
            info['author']['images'] = []
            for size in ((0, 32), (1, 24)):
                url = multi_get(
                    author_info, 'profile_picture_depth_{}'.format(size[0]), 'uri')
                info['author']['images'].append(
                    Image(url, size[1], size[1]).json())

        # author_badges = info.pop('author_badges', None)
        # if author_badges:
        #     info['author']['badges'] = author_badges

        in_reply_to = info.pop('comment_parent', None)
        if isinstance(in_reply_to, dict) and in_reply_to:
            info['in_reply_to'] = FacebookChatDownloader._parse_live_stream_node(
                in_reply_to)

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

    def _get_live_chat_messages_by_video_id(self, video_id, params):
        max_attempts = params.get('max_attempts')
        retry_timeout = params.get('retry_timeout')

        buffer_size = 25  # max num comments returned by api call
        # cursor = ''
        variables = {
            'videoID': video_id
        }
        data = {
            'variables': json.dumps(variables),
            'doc_id': '4889623951078943',  # specifies what API call this is?
            # 'cursor' : cursor
            # &first=12&after=<end_cursor>
        }
        data.update(self.data)
        # p = (), params=p

        first_try = True

        last_ids = []
        while True:

            json_data = self._attempt_fb_retrieve(
                self._GRAPH_API,
                max_attempts,
                retry_timeout,
                headers=self._FB_HEADERS, data=data
            )

            feedback = multi_get(json_data, 'data', 'video', 'feedback') or {}
            if not feedback:
                print('no feedback')  # TODO debug
                print(json_data, flush=True)
                continue

            top_level_comments = multi_get(
                json_data, 'data', 'video', 'feedback', 'top_level_comments')
            edges = top_level_comments.get('edges')[::-1]  # reverse order

            errors = json_data.get('errors')
            if errors:
                # TODO will usually resume getting chat..
                # maybe add timeout?
                print('ERRORS DETECTED')
                print(errors)
                continue
            # TODO - get pagination working
            # page_info = top_level_comments.get('page_info')
            # after = page_info.get('end_cursor')
            num_to_add = 0
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
                    # print('=', end='', flush=True)
                    continue

                last_ids.append(comment_id)

                last_ids = last_ids[-buffer_size:]  # force x items

                if not node:
                    # TODO debug
                    print('no node', edge)
                    continue

                parsed_node = FacebookChatDownloader._parse_live_stream_node(
                    node)
                # TODO determine whether to add or not

                num_to_add += 1

                yield parsed_node

            # got 25 items, and this isn't the first one
            if num_to_add >= buffer_size and not first_try:
                log(
                    'warning',
                    'Messages may be coming in faster than requests are being made.'
                )

            if not top_level_comments:
                print('err2')
                print(json_data)

            if first_try:
                first_try = False

    def _get_chat_replay_messages_by_video_id(self, video_id, max_duration, params):

        max_attempts = params.get('max_attempts')
        retry_timeout = params.get('retry_timeout')

        # useful tool (convert curl to python request)
        # https://curl.trillworks.com/
        # timeout_duration = 10  # TODO make this modifiable

        initial_request_params = (
            ('eft_id', video_id),
            ('target_ufi_instance_id', 'u_2_1'),
            # ('should_backfill', 'false'), # used when seeking? - # TODO true on first try?
        )

        time_increment = 60  # Facebook gets messages by the minute
        # TODO make this modifiable

        start_time = ensure_seconds(
            params.get('start_time'), 0)
        end_time = ensure_seconds(
            params.get('end_time'), float('inf'))

        next_start_time = max(start_time, 0)
        end_time = min(end_time, max_duration)

        # print(next_start_time, end_time, type(next_start_time), type(end_time))
        # return
        # total = []
        while True:
            next_end_time = min(next_start_time + time_increment, end_time)
            times = (('start_time', next_start_time),
                     ('end_time', next_end_time))

            # print(times, flush=True)

            request_params = initial_request_params + times

            json_data = self._attempt_fb_retrieve(
                self._VOD_COMMENTS_API,
                max_attempts,
                retry_timeout,
                True,
                headers=self._FB_HEADERS, params=request_params, data=self.data
            )

            payloads = multi_get(json_data, 'payload', 'ufipayloads')
            if not payloads:

                continue
                # TODO debug
                # print('no comments between',next_start_time, next_end_time, flush=True)
                # print('err1')
                # print(json_data)

            next_start_time = next_end_time

            if next_start_time >= end_time:
                print('end')
                return

            for payload in payloads:
                time_offset = payload.get('timeoffset')
                # print(test)

                ufipayload = payload.get('ufipayload')
                if not ufipayload:
                    print('no ufipayload', payload)
                    continue

                # ['comments'][0]['body']['text']
                comment = multi_get(ufipayload, 'comments', 0)
                if not comment:
                    # TODO debug
                    continue

                # pinned_comments = ufipayload.get('pinnedcomments')
                profile = try_get_first_value(ufipayload['profiles'])

                text = comment['body']['text']  # safe_convert_text()

                temp = {
                    'author': {
                        'name': profile.get('name')
                    },
                    'time_in_seconds': time_offset,
                    'time_text': seconds_to_time(time_offset),
                    'message': text
                }

                yield temp

    def _get_chat_by_video_id(self, match, params):
        return self.get_chat_by_video_id(match.group('id'), params)

    def get_chat_by_video_id(self, video_id, params):

        initial_info = self._get_initial_info(video_id, params)

        start_time = params.get('start_time')
        end_time = params.get('end_time')

        is_live = initial_info.get('is_live')

        # if start or end time specified, use chat replay...
        # The tool works for both active and finished live streams.
        # if start/end time are specified, vods will be prioritised
        # if is live stream and no start/end time specified
        if is_live and not start_time and not end_time:
            generator = self._get_live_chat_messages_by_video_id(
                video_id, params)
        else:
            max_duration = initial_info.get('duration', float('inf'))
            generator = self._get_chat_replay_messages_by_video_id(
                video_id, max_duration, params)

        return Chat(
            generator,
            title=initial_info.get('title'),
            duration=initial_info.get('duration'),
            is_live=is_live,
            author=initial_info.get('author'),
        )
