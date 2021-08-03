
from .common import (
    BaseChatDownloader,
    Chat,
    Remapper as r
)

from ..utils.core import (
    multi_get,
    int_or_none,
    attempts,
    try_parse_json,
    try_get_first_value,
    get_title_of_webpage,
    chunks,
    ensure_seconds,
    seconds_to_time,
    regex_search
)


from ..errors import (
    SiteError,
    VideoNotFound,
    UnexpectedError,
    ChatDisabled
)

from ..debugging import (
    log,
    debug_log
)


from requests.exceptions import RequestException
from json.decoder import JSONDecodeError
import random
import json
import websocket
import time
import re


class RedditError(SiteError):
    """Raised when an error occurs with a Reddit video."""
    pass


class RedditChatDownloader(BaseChatDownloader):

    _REDDIT_HOMEPAGE = 'https://www.reddit.com'
    _INITIAL_INFO_REGEX = r'(?:window\.___r)\s*=\s*({.+?})\s*;<\/script>'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        max_attempts = 3

        for attempt_number in attempts(max_attempts):
            initial_data = self._session_get(self._REDDIT_HOMEPAGE).text

            info = regex_search(initial_data, self._INITIAL_INFO_REGEX)
            if info:
                info = try_parse_json(info)
                break
            else:
                title = get_title_of_webpage(initial_data)
                self.retry(attempt_number, text=title,
                           max_attempts=max_attempts)
                continue

        bearer = multi_get(info, 'user', 'session', 'accessToken')

        self.authed_headers = {
            'authorization': f'Bearer {bearer}',
            **self.session.headers
        }

    _NAME = 'reddit.com'

    _SITE_DEFAULT_PARAMS = {
        'format': 'default',  # TODO create reddit format
    }

    _TESTS = [
        # Different URLS
        {
            'name': 'Get chat messages from past broadcast #1',
            'params': {
                'url': 'https://www.reddit.com/rpan/r/pan/f6zbwb',
                'max_messages': 10
            },
            'expected_result': {
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },


        {
            'name': 'Get chat messages from past broadcast #2',
            'params': {
                'url': 'https://www.reddit.com/rpan/f6vx11',
                'max_messages': 10
            },
            'expected_result': {
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },
        {
            'name': 'Get chat messages from past broadcast #3',
            'params': {
                'url': 'https://www.reddit.com/r/pan/comments/fkzhjg',
                'max_messages': 10
            },
            'expected_result': {
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },
        {
            'name': 'Get chat messages from past broadcast #4',
            'params': {
                'url': 'https://www.reddit.com/comments/fox5px',
                'max_messages': 10
            },
            'expected_result': {
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },
        {
            'name': 'Get chat messages from past broadcast #5',
            'params': {
                'url': 'https://www.reddit.com/lmvsbl',
                'max_messages': 10
            },
            'expected_result': {
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },
        {
            'name': 'Chat replay with start and end times #1',
            'params': {
                'url': 'https://www.reddit.com/rpan/r/pan/lmvsbl',
                'start_time': 123,
                'end_time': 456,
            },
            'expected_result': {
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },
        {
            'name': 'Chat replay with start and end times #2',
            'params': {
                'url': 'https://www.reddit.com/rpan/r/pan/lmvsbl',
                'start_time': 600,
                'end_time': 900,
            },
            'expected_result': {
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },
        # Anomalies
        {
            'name': 'Connection issues',
            'params': {
                'url': 'https://www.reddit.com/r/talentShow/comments/ofkm5s/carving_a_wood_vase/',
                'timeout': 5
            }
        },
        {
            'name': "This broadcast programme is off-air (has not started or has ended)",
            'params': {
                'url': 'https://www.reddit.com/rpan/r/RedditMasterClasses/olw6ww',
                'timeout': 5
            }
        },

        # Subreddits:
        {
            'name': 'Get chat of top livestream/post for subreddit #1',
            'params': {
                'url': 'https://www.reddit.com/rpan/r/pan',
                'timeout': 5
            }
        },
        {
            'name': 'Get chat of top livestream/post for subreddit #2',
            'params': {
                'url': 'https://www.reddit.com/r/RedditSessions',
                'timeout': 5
            }
        }
    ]

    # Regex provided by youtube-dl

    _VALID_URLS = {
        '_get_chat_by_subreddit_id': r'(?:https?://(?:[^/]+\.))reddit\.com/(?:(?:rpan/r|r)/)+(?P<id>[^/?#&\s]+)/?$',
        '_get_chat_by_post_id': r'(?:https?://(?:[^/]+\.))reddit\.com/(?:(?:rpan/r/[^/]+|rpan|r/[^/]+/comments|rpan|comments)/)*(?P<id>[^/?#&\s]+)',
    }

    _REMAPPING = {

        # Shared
        'author': 'author_name',
        'name': 'message_id',

        'link_id': 'post_id',

        'author_fullname': 'author_id',
        'subreddit_id': 'subreddit_id',
        'subreddit_name_prefixed': 'subreddit_name_prefixed',
        'subreddit': 'subreddit',

        'body': 'message',
        'body_html': 'message_html',

        'author_flair_type': 'author_flair_type',
        'author_flair_text_color': 'author_flair_text_color',
        'author_flair_text': 'author_flair_text',
        'author_flair_background_color': 'author_flair_background_color',

        'score': 'score',
        'created_utc': r('timestamp', lambda x: int(x * 1000000)),

        # 'author_flair_template_id':null,
        # "comment_type":null,
        # "flair_css_class":"flair-None",
        # "collapsed":false,
        # "author_flair_richtext":[],
        # "associated_award":null,
        # "distinguished":null

        # Live (websockets)
        'author_icon_img': 'author_profile_img',  # TODO parse into sizes
        'author_snoovatar_img': 'author_snoovatar_img',
        'author_is_default_icon': 'author_is_default_icon',
        'author_is_nsfw_icon': 'author_is_nsfw_icon',

        'context': r('url', lambda x: RedditChatDownloader._REDDIT_HOMEPAGE+x),

        # "attribs":[],
        # "rtjson":{...},
        # "full_date":"2021-07-17T00:20:29+00:00",
        # "collapsed_in_crowd_control":false,
        # "total_comment_count":53,
        # "flair_position":"right",
        # "_id36":"h5gn4k1",
        # "author_id":65099537,

        # Past broadcasts (API)
        'permalink': r('url', lambda x: RedditChatDownloader._REDDIT_HOMEPAGE+x),
        'total_awards_received': 'total_awards_received',
        'edited': 'is_edited',

        'parent_id': 'parent_message_id',

        'ups': 'upvotes',
        'downs': 'downvotes',

        'controversiality': 'controversiality',

        # "approved_at_utc":null,
        # "mod_reason_by":null,
        # "banned_by":null,
        # "removal_reason":null,
        # "likes":null,
        # "replies":"",
        # "user_reports":[],
        # "saved":false,
        # "banned_at_utc":null,
        # "mod_reason_title":null,
        # "gilded":0,
        # "archived":false,
        # "collapsed_reason_code":null,
        # "no_follow":true,
        # "can_mod_post":false,
        # "send_replies":true,
        # "approved_by":null,
        # "mod_note":null,
        # "all_awardings":[],
        # "awarders":[],
        # "author_patreon_flair":false,
        # "created":1625701905.0,
        # "is_submitter":false,
        # "gildings":{},
        # "collapsed_reason":null,
        # "stickied":false,
        # "author_premium":false,
        # "can_gild":false,
        # "top_awarded_type":null,
        # "score_hidden":false,
        # "num_reports":null,
        # "locked":false,
        # "report_reasons":null,
        # "treatment_tags":[],
        # "collapsed_because_crowd_control":null,
        # "mod_reports":[],
        # "subreddit_type":"public",

    }

    _KNOWN_MESSAGE_TYPES = ['new_comment', 'delete_comment',
                            'remove_comment', 'update_comment_score']

    @ staticmethod
    def _parse_item(item, start_time=None):

        info = r.remap_dict(item, RedditChatDownloader._REMAPPING)

        BaseChatDownloader._move_to_dict(info, 'author')

        author_name = multi_get(info, 'author', 'name')
        if author_name:
            info['author_display_name'] = author_name

        if isinstance(start_time, (float, int)):
            info['time_in_seconds'] = (info['timestamp'] - start_time)/1e6
            info['time_text'] = seconds_to_time(info['time_in_seconds'])

        return info

    def _get_chat_by_subreddit_id(self, match, params):
        match_id = match.group('id')
        return self.get_chat_by_subreddit_id(match_id, params)

    def _get_chat_by_post_id(self, match, params):
        match_id = match.group('id')
        return self.get_chat_by_post_id(match_id, params)

    def _try_get_info(self, url, program_params, **kwargs):
        max_attempts = program_params.get('max_attempts')
        for attempt_number in attempts(max_attempts):
            try:
                return self._session_get_json(url, **kwargs)
            except (JSONDecodeError, RequestException) as e:
                self.retry(attempt_number, error=e, **program_params)

    _API_TEMPLATE = 'https://strapi.reddit.com/videos/t3_{}'

    _STATE_REMAPPING = {
        'IS_LIVE': 'live',
        'NOT_STARTED': 'upcoming',
        'ENDED': 'past'
    }

    def get_chat_by_post_id(self, post_id, params, attempt_number=0, initial_info=None):

        if initial_info is None:  # Optimisation
            initial_info = self._try_get_info(self._API_TEMPLATE.format(
                post_id), params, headers=self.authed_headers)

        status = initial_info.get('status')
        status_message = initial_info.get('status_message')
        data = initial_info.get('data')

        if status == 'success':
            chat_disabled = data.get('chat_disabled')
            if chat_disabled:
                raise ChatDisabled('Chat is disabled for this stream.')

            post_info = data.get('post')

            stream_info = data.get('stream')

            if not stream_info:
                raise RedditError(f'Stream info not found: {data}')

            title = post_info.get('title')

            start_time = (stream_info.get('hls_exists_at') or stream_info.get(
                'publish_at') or stream_info.get('update_at'))
            if start_time:
                start_time *= 1000

            socket_url = post_info.get('liveCommentsWebsocket')

            live_status = self._STATE_REMAPPING.get(stream_info.get('state'))

            chat_item = Chat(title=title,
                             status=live_status,
                             video_type='video',
                             start_time=start_time,
                             id=post_id)

            if live_status in ('live', 'upcoming') and socket_url:  # live stream

                if not socket_url.startswith('wss://') or 'wss.redditmedia.com' not in socket_url:
                    self.retry(
                        attempt_number, text=f'Invalid websocket URL: {socket_url}', **params)
                    return self.get_chat_by_post_id(post_id, params, attempt_number + 1)

                chat_item.chat = self._get_chat_messages_by_socket(
                    socket_url, params)

            else:  # replay
                chat_item.chat = self._get_chat_messages_by_post_id(
                    post_id, params, start_time)

            return chat_item

        elif status == 'failure':
            if isinstance(data, str) and 'wait' in data.lower():
                message = f'Response from Reddit: "{data}"'
                self.retry(attempt_number, text=message, **params)
                return self.get_chat_by_post_id(post_id, params, attempt_number + 1)

            raise RedditError(data)

        elif status == 'video not found':
            raise VideoNotFound('Video not found')

        else:  # Unknown
            raise UnexpectedError(f'Info: {initial_info}')

    def _get_chat_messages_by_socket(self, socket_url, params):

        message_receive_timeout = params.get('message_receive_timeout')
        max_attempts = params.get('max_attempts')

        def create_connection():
            for attempt_number in attempts(max_attempts):
                try:
                    log('debug', f'Connecting to socket: {socket_url}')
                    ws = websocket.create_connection(socket_url)

                    # timeout needed for polling (allow keyboard interrupts)
                    ws.settimeout(message_receive_timeout)
                    return ws
                except (ConnectionError, websocket.WebSocketException) as e:
                    self.retry(attempt_number, error=e, **params)

        ws = create_connection()

        try:
            while True:
                try:
                    opcode, raw_data = ws.recv_data()
                    data = json.loads(raw_data)

                    message_type = data.get('type')

                    if message_type in self._KNOWN_MESSAGE_TYPES:
                        payload = data.get('payload')

                        parsed = self._parse_item(payload)
                        parsed['message_type'] = message_type

                        yield parsed

                    else:
                        debug_log(
                            f'Unknown message type: {message_type}', data)

                except websocket.WebSocketTimeoutException:
                    pass

                except (ConnectionError, websocket.WebSocketException):
                    # Close old connection
                    ws.close()

                    # Create a new connection
                    ws = create_connection()

        finally:
            ws.close()

    _COMMENTS_API_TEMPLATE = 'https://www.reddit.com/comments/{}/.json?limit=1'  # &sort=old

    def _get_chat_messages_by_post_id(self, post_id, params, stream_start_time=None):

        # 1. Get all comment ids
        url = self._COMMENTS_API_TEMPLATE.format(post_id)
        initial_info = self._try_get_info(url, params)

        children = multi_get(initial_info, -1, 'data', 'children')

        first_id = multi_get(children, 0, 'data', 'id')
        comment_ids = multi_get(children, -1, 'data', 'children') or []

        if first_id:
            comment_ids.insert(0, first_id)

        if not comment_ids:
            return  # No comments

        comment_ids.sort()

        num_comments = len(comment_ids)
        log('debug', f'Found {num_comments} messages')

        # https://www.reddit.com/dev/api/#GET_api_info
        info_api = 'https://www.reddit.com/api/info.json?raw_json=1&id=t1_'

        chunk_size = 100

        chunk_info = list(chunks(comment_ids, chunk_size))
        num_bins = len(chunk_info)
        all_stored = [{} for x in range(num_bins)]

        def _parse_chunk(index):
            if not all_stored[index]:  # get if not stored
                url = info_api + ',t1_'.join(chunk_info[index])
                info = self._try_get_info(url, params)
                children = multi_get(info, 'data', 'children') or []
                all_stored[index] = [self._parse_item(
                    child.get('data'), stream_start_time) for child in children]

            return all_stored[index]

        start_time = ensure_seconds(
            params.get('start_time'))
        end_time = ensure_seconds(
            params.get('end_time'), float('inf'))

        start_chunk_index = 0

        if start_time is None:
            start_time = float('-inf')

        else:
            utc_start_time = start_time*1e6 + \
                (stream_start_time or time.time()*1e3)

            def _binary_search(low, high):

                if high < low:
                    return -1

                mid = (high + low) // 2
                parsed_mid_chunk = _parse_chunk(mid)

                ts_min = multi_get(parsed_mid_chunk, 0, 'timestamp') or 0
                ts_max = multi_get(parsed_mid_chunk, -1,
                                   'timestamp') or float('inf')

                if ts_min <= utc_start_time <= ts_max:
                    return mid
                elif utc_start_time < ts_min:
                    return _binary_search(low, mid - 1)
                else:  # ts_max > utc_start_time:
                    return _binary_search(mid + 1, high)

            start_chunk_index = _binary_search(0, num_bins)

        count = 0
        # Process remaining chunks
        for index, chunk in enumerate(chunk_info):
            if index < start_chunk_index:
                continue

            for item in _parse_chunk(index):
                if item['time_in_seconds'] > end_time:
                    return

                if start_time <= item['time_in_seconds']:
                    yield item
                    count += 1

            log('debug', f'Total number of messages: {count}')

    _BROADCAST_API_URL = 'https://strapi.reddit.com/broadcasts'
    _SUBREDDIT_BROADCAST_API_URL = 'https://strapi.reddit.com/r/{}/broadcasts?page_size=1'

    def get_chat_by_subreddit_id(self, subreddit_id, params, attempt_number=0):
        # Get chat of top broadcast
        initial_info = self._try_get_info(self._SUBREDDIT_BROADCAST_API_URL.format(
            subreddit_id), params, headers=self.authed_headers)

        status = initial_info.get('status')
        data = initial_info.get('data')

        if status == 'success':
            post_id = initial_info.get('next_cursor')

            data = initial_info.pop('data', [])
            if not data:
                raise RedditError('This subreddit has no broadcasts.')

            initial_info['data'] = data[0]

            return self.get_chat_by_post_id(post_id, params, initial_info=initial_info)

        elif status == 'failure':
            if isinstance(data, str) and 'wait' in data.lower():
                message = f'Response from Reddit: "{data}"'
                self.retry(attempt_number, text=message, **params)
                return self.get_chat_by_subreddit_id(subreddit_id, params, attempt_number + 1)

            raise RedditError(data)

        else:  # Unknown
            raise UnexpectedError(f'Info: {initial_info}')

    _RPAN_API_URL = 'https://www.reddit.com/r/{}/new.json'

    # RPAN subreddits
    # https://en.wikipedia.org/wiki/Reddit_Public_Access_Network
    # Broadcasting is being rolled out to more and more subreddits, but the following are the official RPAN subreddits:
    _RPAN_SUBREDDITS = ['AnimalsOnReddit', 'DistantSocializing', 'GlamourSchool',
                        'HeadlineWorthy', 'LGBT', 'ReadWithMe', 'RedditInTheKitchen',
                        'RedditMasterClasses', 'RedditSessions', 'RedditSets',
                        'ShortCircuit', 'TalentShow', 'TheArtistStudio',
                        'TheGamerLounge', 'TheYouShow', 'WhereIntheWorld', 'pan']

    # 'TheRedditStudio' - {"reason": "private", "message": "Forbidden", "error": 403}

    def generate_urls(self, **program_params):
        # TODO add sort-by-viewers option
        # TODO add options for live and past

        max_attempts = program_params.get('max_attempts')

        # Get live streams
        for attempt_number in attempts(max_attempts):
            message = None
            error = None

            try:
                info = self._session_get_json(
                    self._BROADCAST_API_URL, headers=self.authed_headers)

                data = info.get('data')

                if isinstance(data, list):  # success
                    break

                message = f'Response from Reddit: "{data}"'

            except (JSONDecodeError, RequestException) as e:
                error = e

            self.retry(attempt_number, error=error,
                       text=message, **program_params)

        for stream in data:
            yield multi_get(stream, 'post', 'url')

        # Get previous broadcasts

        limit = 100

        past_params = {
            'sort': 'old',
            'limit': limit
        }

        api_url = self._RPAN_API_URL.format(
            random.choice(self._RPAN_SUBREDDITS))
        count = 0
        while True:
            rpan_info = self._try_get_info(
                api_url, program_params, params=past_params)

            rpan_data = rpan_info.get('data')
            if not rpan_data:
                break

            children = rpan_data.get('children') or []

            for child in children:
                data = child.get('data')
                url = data.get('permalink')

                if url and 'rpan_video' in data:

                    yield self._REDDIT_HOMEPAGE + url

                    count += 1
                    if count >= limit:  # TODO to remove?
                        return

            past_params['after'] = rpan_data.get('after')
            if not past_params['after']:
                break
