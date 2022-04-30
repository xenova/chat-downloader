from .common import (
    Chat,
    BaseChatDownloader,
    Remapper as r,
    Image
)
from ..utils.core import (
    remove_prefixes,
    multi_get,
    seconds_to_time,
    camel_case_split,
    ensure_seconds,
    attempts,
    regex_search,
    base64_encode,
)
from ..utils.timed_utils import interruptible_sleep

from ..errors import (
    SiteError,
    VideoUnavailable,
    LoginRequired
)

from ..debugging import (log, debug_log)

import json
import re
from json.decoder import JSONDecodeError
from requests.exceptions import RequestException


class FacebookError(SiteError):
    """Raised when an error occurs with a Facebook video."""
    pass


class RateLimitError(FacebookError):
    """Raised when the user has been rate-limited."""
    pass


class FacebookChatDownloader(BaseChatDownloader):
    _FB_HOMEPAGE = 'https://www.facebook.com'

    _INITIAL_DATR_REGEX = r'_js_datr\",\"([^\"]+)'
    _INITIAL_LSD_REGEX = r'<input.*?name=\"lsd\".*?value=\"([^\"]+)[^>]*>'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # update headers for all subsequent FB requests
        self.update_session_headers({
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': self._FB_HOMEPAGE,  # Required'
        })

        initial_data = self._session_get(self._FB_HOMEPAGE).text

        datr = regex_search(initial_data, self._INITIAL_DATR_REGEX)
        if not datr:
            raise FacebookError(f'Unable to set datr cookie: {initial_data}')

        self.set_cookie_value('.facebook.com', 'datr', datr)
        self.set_cookie_value('.facebook.com', 'wd', '1920x1080')

        lsd = regex_search(initial_data, self._INITIAL_LSD_REGEX)
        if not lsd:
            raise FacebookError(f'Unable to set lsd cookie: {initial_data}')

        self.lsd = lsd
        self.update_session_headers({
            'x-fb-lsd': lsd,
            'upgrade-insecure-requests': '1',
            'cache-control': 'max-age=0'
        })

    _NAME = 'facebook.com'
    # Regex provided by youtube-dl

    _VALID_URLS = {
        '_get_chat_by_video_id': r'''(?x)
            (?:
                https?://
                    (?:[\w-]+\.)?(?:facebook\.com)/
                    (?:[^#]*?\#!/)?
                    (?:[^/]+/videos/(?:[^/]+/)?|video\.php\?v=)
            )
            (?P<id>[0-9]+)
            '''
    }

    _TESTS = [
        {
            'name': 'Get chat messages from past gaming broadcast',
            'params': {
                'url': 'https://www.facebook.com/disguisedtoast/videos/3629284013844544/',
                'max_messages': 100
            },
            'expected_result': {
                'messages_condition': lambda messages: 0 < len(messages) <= 100,
            }
        },

        {
            'name': 'Get chat messages from gaming clip',
            'params': {
                'url': 'https://www.facebook.com/disguisedtoast/videos/1170480696709027/',
                'max_messages': 100
            },
            'expected_result': {
                'messages_condition': lambda messages: 0 < len(messages) <= 100,
            }
        },

        {
            'name': 'Get chat messages from short gaming video',
            'params': {
                'url': 'https://www.facebook.com/disguisedtoast/videos/333201981735004/',
                'max_messages': 100
            },
            'expected_result': {
                'messages_condition': lambda messages: 0 < len(messages) <= 100,
            }
        },

        {
            'name': 'Get chat messages from long gaming video',
            'params': {
                'url': 'https://www.facebook.com/disguisedtoast/videos/918814568681983/',
                'start_time': 60,
                'end_time': 150
            },
            'expected_result': {
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },

        {
            'name': 'Get chat messages from video page',
            'params': {
                'url': 'https://www.facebook.com/video.php?v=570133851026337',
                'max_messages': 100
            },
            'expected_result': {
                'messages_condition': lambda messages: 0 < len(messages) <= 100,
            }
        },
        {
            'name': 'Get chat messages from short video',
            'params': {
                'url': 'https://www.facebook.com/338233632988842/videos/958020308373031',
                'max_messages': 100
            },
            'expected_result': {
                'messages_condition': lambda messages: 0 < len(messages) <= 100,
            }
        },
        {
            'name': 'Get chat messages from past broadcast',
            'params': {
                'url': 'https://www.facebook.com/kolaolootulive/videos/553617129001138/',
                'start_time': 567,
                'end_time': 1234
            },
            'expected_result': {
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },

        # Check for errors
        {
            'name': 'Video unavailable or private',
            'params': {
                'url': 'https://www.facebook.com/SRAVS.Gaming/videos/512714596679251/',
            },
            'expected_result': {
                'error': VideoUnavailable,
            }
        },
    ]
    _TESTS = [] # Remove support for facebook
    _GRAPH_API = _FB_HOMEPAGE + '/api/graphql/'

    def _graphql_request(self, program_params, retry_on_error=True, **post_kwargs):
        data = {
            'av': '0',
            '__user': '0',
            '__a': '1',
            '__comet_req': '1',
            'lsd': self.lsd,
            'server_timestamps': 'true',
            '__csr': '',
            'dpr': '1',
            '__ccg': 'MODERATE',
        }
        data.update(post_kwargs.pop('data', {}))
        post_kwargs['data'] = data

        max_attempts = program_params.get('max_attempts')
        for attempt_number in attempts(max_attempts):
            try:
                response = self._session_post(self._GRAPH_API, **post_kwargs)
                response_json = response.json()

                # Check for errors
                for error in response_json.get('errors') or []:
                    if error.get('code') == 1675004:
                        raise RateLimitError(f'Rate limit exceeded: {error}')

                return response_json

            except JSONDecodeError as e:
                self.retry(attempt_number, error=e, **program_params,
                           text=f'Unable to parse JSON: `{response.text}`')

            except RequestException as e:
                self.retry(attempt_number, error=e, **program_params)

            except RateLimitError as e:
                if retry_on_error:
                    self.retry(attempt_number, error=e, **program_params)
                else:
                    raise e

    _VIDEO_TITLE_REGEX = r'<meta\s+name=["\'].*title["\']\s+content=["\']([^"\']+)["\']\s*/>'

    def _get_initial_info(self, video_id, program_params):

        # Get metadata
        data = {
            'variables': json.dumps({
                'upNextVideoID': video_id,
            }),
            'doc_id': '4730353697015342'
        }

        json_data = self._graphql_request(program_params, data=data)

        video_data = multi_get(json_data, 'data', 'upNextVideoData')
        if not video_data:
            log('debug', json_data)
            raise VideoUnavailable('Video unavailable')

        return {
            'status': 'live' if video_data.get('is_live_streaming') else 'past',
            'video_type': 'video',
            'broadcast_status': video_data.get('broadcast_status'),
            'title': video_data.get('title_with_fallback'),
            'username': multi_get(video_data, 'owner', 'name'),
            'start_time': video_data.get('publish_time') * 1000000,
            'duration': video_data.get('playable_duration')
        }

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
    def _get_url(item):
        return item.get('url')

    @staticmethod
    def _parse_attachment_info(original_item):

        if isinstance(original_item, (list, tuple)) and len(original_item) > 0:
            original_item = original_item[0]

        if not original_item:
            return {}

        item = r.remap_dict(
            original_item, FacebookChatDownloader._TARGET_MEDIA_REMAPPING)

        # VideoTipJarPayment
        quantity = item.get('quantity')
        if quantity:
            item['text'] = f"Sent {quantity} Star{'s' if quantity != 1 else ''}"

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

            item = r.remap_dict(
                entity, FacebookChatDownloader._TARGET_MEDIA_REMAPPING)
            item['text'] = donation_comment_text.get('text')

        # DEBUGGING
        original_type_name = original_item.get('__typename')
        if original_type_name not in FacebookChatDownloader._KNOWN_ATTACHMENT_TYPES:
            debug_log(
                f'Unknown attachment type: {original_type_name}',
                original_item,
                item
            )

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

    @staticmethod
    def _parse_attachment_renderer(item):
        attachment = multi_get(item, 'style_type_renderer',
                               'attachment') or item.get('attachment')
        if not attachment:
            debug_log(f'No attachment: {item}')
            return {}

        return FacebookChatDownloader._parse_attachment(attachment)

    @staticmethod
    def _parse_attachment(attachment):
        parsed = r.remap_dict(
            attachment, FacebookChatDownloader._ATTACHMENT_REMAPPING)

        for key in ('target', 'media', 'style_infos'):
            if parsed.get(key) == {}:
                parsed.pop(key)

        missing_keys = attachment.keys() - FacebookChatDownloader._KNOWN_ATTACHMENT_KEYS
        if missing_keys:
            debug_log(
                f'Missing attachment keys: {missing_keys}',
                attachment,
                parsed
            )

        return parsed

    _ATTACHMENT_REMAPPING = {
        'url': 'url',  # facebook redirect url,
        'source': r('source', _get_text),
        'title_with_entities': r('title', _get_text),

        'target': r('target', _parse_attachment_info),
        'media': r('media', _parse_attachment_info),
        'style_infos': r('style_infos', _parse_attachment_info),

        'attachment_text': r('text', _get_text),

        '__typename': 'type',

        'story_url': 'story_url',
        'story_attachment_link_renderer': r('story_attachment', _parse_attachment_renderer),

        'web_link': r('web_link', _get_url)
        # 'sticker_image': r('sticker_image', _get_uri),


    }

    _IGNORE_ATTACHMENT_KEYS = [
        'tracking',
        'action_links',
        'third_party_media_info'
    ]

    _KNOWN_ATTACHMENT_KEYS = set(
        list(_ATTACHMENT_REMAPPING.keys()) + _IGNORE_ATTACHMENT_KEYS)

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
        'Video',

        'Group',
        'ProfilePicAttachmentMedia',
        'User',
        'Photo',

        'ExternalUrl',
        'GenericAttachmentMedia',

        'ChatCommandResult',

        'CommentMessageInfo',
        'FundraiserForStoryDonationAttachmentStyleInfo',

        'Event'
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


        'timestamp_in_video': 'timestamp_in_video',
        'written_while_video_was_live': 'written_while_video_was_live',



        'translatability_for_viewer': r('message_dialect', lambda x: x.get('source_dialect_name')),


        'url': 'message_url',

        'body': r('message', _get_text),

        'identity_badges_web': r('author_badges', lambda x: list(map(FacebookChatDownloader._parse_author_badges, x))),

        'attachments': r('attachments', lambda x: list(map(FacebookChatDownloader._parse_attachment_renderer, x)))

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
    def _parse_node(node, parse_time=False, start_time=None):
        info = r.remap_dict(node, FacebookChatDownloader._REMAPPING)

        author_info = info.pop('author', {})
        BaseChatDownloader._move_to_dict(
            info, 'author', create_when_empty=True)

        info['author'] = r.remap_dict(
            author_info, FacebookChatDownloader._AUTHOR_REMAPPING)

        if 'profile_picture_depth_0' in author_info:
            info['author']['images'] = []
            for size in ((0, 32), (1, 24)):
                url = multi_get(
                    author_info, f'profile_picture_depth_{size[0]}', 'uri')
                info['author']['images'].append(
                    Image(url, size[1], size[1]).json())

        # author_badges = info.pop('author_badges', None)
        # if author_badges:
        #     info['author']['badges'] = author_badges

        in_reply_to = info.pop('comment_parent', None)
        if isinstance(in_reply_to, dict) and in_reply_to:
            info['in_reply_to'] = FacebookChatDownloader._parse_node(
                in_reply_to, parse_time, start_time)

        if parse_time:
            timestamp_in_video = info.get('timestamp_in_video')
            if timestamp_in_video is not None:
                if start_time is None:
                    info['time_in_seconds'] = timestamp_in_video
                else:
                    info['time_in_seconds'] = (
                        info['timestamp'] - start_time)/1e6

                info['time_text'] = seconds_to_time(info['time_in_seconds'])

        message = info.get('message')
        if message:
            info['message'] = message
            info['message_type'] = 'text_message'
        else:
            info.pop('message', None)  # remove if empty

        # remove the following if empty:
        if info.get('reactions') == {}:
            info.pop('reactions')
        if info.get('attachments') == []:
            info.pop('attachments')

        return info

    def _get_live_chat_messages_by_video_id(self, video_id, params):
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

        first_try = True

        last_ids = []
        while True:

            json_data = self._graphql_request(params, data=data)

            feedback = multi_get(json_data, 'data', 'video', 'feedback')
            if not feedback:
                log('debug', f'No feedback: {json_data}')
                continue

            top_level_comments = multi_get(
                json_data, 'data', 'video', 'feedback', 'top_level_comments')

            errors = json_data.get('errors')
            if errors:
                # TODO will usually resume getting chat..
                # maybe add timeout?
                log('debug', f'Errors detected: {errors}')
                continue

            if not top_level_comments:
                log('debug', f'No top level comments: {json_data}')
                continue

            # Parse items:
            parsed_items = []
            for edge in top_level_comments.get('edges') or []:
                node = edge.get('node')
                if not node:
                    log('debug', f'No node found in edge: {edge}')
                    continue
                parsed_items.append(FacebookChatDownloader._parse_node(node))

            # Sort items
            parsed_items.sort(key=lambda x: x['timestamp'])

            # TODO - get pagination working
            # page_info = top_level_comments.get('page_info')
            # after = page_info.get('end_cursor')
            # has_next_page = page_info.get('has_next_page')

            num_to_add = 0
            for item in parsed_items:
                comment_id = item.get('message_id')

                # remove items that have already been parsed
                if comment_id in last_ids:
                    continue

                last_ids.append(comment_id)
                last_ids = last_ids[-buffer_size:]  # force x items

                # TODO determine whether to add or not (message types/groups)

                num_to_add += 1
                yield item

            if num_to_add == 0:
                time_to_sleep = 1
                log('debug',
                    f'No actions, sleeping for {time_to_sleep} seconds')
                interruptible_sleep(time_to_sleep)

            # got 25 items, and this isn't the first one
            if num_to_add >= buffer_size and not first_try:
                log(
                    'warning',
                    'Messages may be coming in faster than requests are being made.'
                )

            if first_try:
                first_try = False


    def _get_chat_from_vod(self, feedback_id, stream_start_time, end_time, params):
        # method 1 - only works for vods. Guaranteed to get all, but can't choose start time
        # ordered by timestamp

        data = {
            'fb_api_req_friendly_name': 'CometUFICommentsProviderPaginationQuery',
            'doc_id': '4310877875602018'
        }

        ordering = 'LIVE_STREAMING'  # 'TOPLEVEL' 'RANKED_THREADED' 'CHRONOLOGICAL'

        variables = {
            'feedLocation': 'TAHOE',
            'feedbackID': feedback_id,
            'feedbackSource': 41,
            'last': 50,  # max step is 50
            'includeHighlightedComments': True,
            'includeNestedComments': True,
            'initialViewOption': ordering,
            'topLevelViewOption': ordering,
            'viewOption': ordering
        }

        before = None
        while True:
            variables['before'] = before
            variables['isPaginating'] = before is not None

            data['variables'] = json.dumps(variables)

            json_data = self._graphql_request(params, retry_on_error=False, data=data)

            info = multi_get(json_data, 'data', 'feedback')
            if not info:
                log('debug', f'No feedback: {json_data}')
                break

            display_comments = info.get('display_comments')
            edges = display_comments.get('edges') or []

            parsed_items = []
            for edge in reversed(edges):
                node = edge.get('node')
                if not node:
                    log('debug', f'No node found in edge: {edge}')
                    continue

                parsed = FacebookChatDownloader._parse_node(
                    node, True, stream_start_time)

                time_in_seconds = parsed.get('time_in_seconds')
                if time_in_seconds is None:
                    continue
                if time_in_seconds > end_time:
                    return
                parsed_items.append(parsed)

            parsed_items.sort(key=lambda x: x['timestamp'])
            yield from parsed_items

            page_info = display_comments.get('page_info') or {}
            if not page_info.get('has_previous_page'):
                break

            before = page_info.get('start_cursor')

    def _get_chat_from_video(self, feedback_id, start_time, end_time, params):
        # method 2 - works for all videos, but sometimes misses comments
        # max messages is 30 per minute
        # ordered by time_in_seconds
        log('debug', 'Running method 2')

        data = {
            'fb_api_req_friendly_name': 'CometLiveVODCommentListRefetchableQuery',
            'doc_id': '3941623715965411'
        }

        # By default, Facebook gets messages by the minute
        time_increment = 600  # 10 mins

        next_start_time = max(start_time, 0)

        variables = {
            'id': feedback_id
        }

        while True:
            next_end_time = min(next_start_time + time_increment, end_time)

            variables['afterTime'] = next_start_time
            variables['beforeTime'] = next_end_time

            data['variables'] = json.dumps(variables)

            json_data = self._graphql_request(params, data=data)

            edges = multi_get(json_data, 'data', 'node',
                              'video_timestamped_comments', 'edges') or []

            for edge in edges:
                node = edge.get('node')
                if not node:
                    log('debug', f'No node found in edge: {edge}')
                    continue
                yield FacebookChatDownloader._parse_node(node, True)

            if next_end_time >= end_time:
                return
            next_start_time = next_end_time

    def _get_chat_replay_messages_by_video_id(self, video_id, max_duration, initial_info, params):
        feedback_id = base64_encode(f'feedback:{video_id}')
        broadcast_status = initial_info.get('broadcast_status')
        stream_start_time = initial_info.get('start_time')

        start_time = ensure_seconds(params.get('start_time'), 0)
        end_time = min(ensure_seconds(params.get(
            'end_time'), float('inf')), max_duration)

        success = False

        if broadcast_status == 'VOD_READY' and params.get('start_time') is None:
            # no start time, get until end_time
            log('debug', 'Running method 1')
            try:
                for i in self._get_chat_from_vod(feedback_id, stream_start_time, end_time, params):
                    time_in_seconds = i.get('time_in_seconds')
                    if time_in_seconds is not None:
                        start_time = max(start_time, time_in_seconds)
                    yield i
                success = True

            except RateLimitError as e:
                pass

        if not success:  # Fallback
            yield from self._get_chat_from_video(feedback_id, start_time, end_time, params)

    def _get_chat_by_video_id(self, match, params):
        return self.get_chat_by_video_id(match.group('id'), params)

    def get_chat_by_video_id(self, video_id, params):

        initial_info = self._get_initial_info(video_id, params)

        start_time = params.get('start_time')
        end_time = params.get('end_time')

        # if start or end time specified, use chat replay...
        # The tool works for both active and finished live streams.
        # if start/end time are specified, vods will be prioritised
        # if is live stream and no start/end time specified
        if initial_info.get('status') == 'live' and not start_time and not end_time:
            generator = self._get_live_chat_messages_by_video_id(
                video_id, params)
        else:
            max_duration = initial_info.get('duration', float('inf'))

            generator = self._get_chat_replay_messages_by_video_id(
                video_id, max_duration, initial_info, params)

        return Chat(
            generator,
            id=video_id,
            **initial_info
        )

    _STREAM_PAGE = 'https://www.facebook.com/gaming/browse/live/?s=VIEWERS&language=ALL_LANG'

    def generate_urls(self, **kwargs):
        yield from self._generate_live(kwargs.get('livestream_limit'), **kwargs)
        yield from self._generate_videos(kwargs.get('vod_limit'), **kwargs)
        yield from self._generate_clips(kwargs.get('clip_limit'), **kwargs)

    def _generate_live(self, limit, **kwargs):
        # https://www.facebook.com/gaming/browse/live/?s=VIEWERS&language=ALL_LANG
        return self._generate_urls('live', limit, **kwargs)

    def _generate_videos(self, limit, **kwargs):
        # https://www.facebook.com/gaming/videos
        return self._generate_urls('videos', limit, **kwargs)

    def _generate_clips(self, limit, **kwargs):
        # https://www.facebook.com/gaming/clips/
        return self._generate_urls('clips', limit, **kwargs)

    def _generate_urls(self, video_type, limit, **kwargs):
        max_attempts = 10
        program_params = {
            'max_attempts': max_attempts
        }

        step = 8
        if video_type in ('live', 'videos'):
            variables = {
                'count': step,
                'params': {
                    'following': None,  # False
                    'game_id': None,
                    'language': 'ALL_LANG',
                    'remove_following': True,
                    'sort_order': 'VIEWERS'  # None 'SUGGESTED'
                }
            }

            key = 'top_live' if video_type == 'live' else 'top_was_live'

        else:  # video_type == 'clips':
            variables = {
                'count': step,
                'following': False,
                'game_id': None,
                'streamer_id': None,
                'sort_order': 'VIEWERS'  # None 'SUGGESTED'
            }
            key = 'top_weekly_clips'

        doc_ids = {
            'live': 3843810065738698,
            'videos': 4591277870888795,
            'clips': 3586924904747093
        }
        doc_id = doc_ids.get(video_type)

        data = {
            'doc_id': doc_id
        }

        count = 0
        while True:
            data['variables'] = json.dumps(variables)

            json_data = self._graphql_request(program_params, data=data)

            top_live = multi_get(json_data, 'data', 'gaming_video', key)

            if not top_live:
                log('debug', f'No data found: {json_data}')
                return

            edges = top_live.get('edges') or []

            for edge in edges:
                if count >= limit:
                    return

                url = multi_get(edge, 'node', 'url')
                if url:
                    yield url
                    count += 1

            page_info = top_live.get('page_info')

            has_next_page = page_info.get('has_next_page')

            if not has_next_page:
                break
            variables['cursor'] = page_info.get('end_cursor')
