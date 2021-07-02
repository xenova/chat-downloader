
from .common import (
    BaseChatDownloader,
    Chat,
    Remapper as r
)

from ..utils import (
    multi_get,
    int_or_none,
    attempts,
    interruptible_sleep
)

from ..errors import (
    YouNowError
)

from requests.exceptions import RequestException
from json.decoder import JSONDecodeError
import hashlib


class YouNowChatDownloader(BaseChatDownloader):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    _NAME = 'younow.com'

    _SITE_DEFAULT_PARAMS = {
        'format': 'default',  # TODO create younow format
    }

    _TESTS = []

    # Regex provided by youtube-dl

    _VALID_URLS = {
        '_get_chat_by_user': r'https?://(?:www\.)?younow\.com/(?P<id>[^/?#&]+)'
    }

    _REMAPPING = {
        'comment': 'message',
        'userId': 'author_id',
        'name': 'author_name',
        'userLevel': 'author_level',
        'profileUrlString': 'author_url',
        'role': 'role',

        'paid': 'is_paid',
        'subscriptionType': 'subscription_type',
        'broadcasterMod': 'is_moderator',
        'optedToGuest': 'is_opted_to_guest',
        'isAmbassador': 'is_ambassador',
        'timestamp': r('timestamp', lambda x: int_or_none(x, 0) * 1000000),

        # Other keys not currently in use:
        #  'isPrivate':0,
        #  'broadcasterTierRank':3,
        #  'globalSpenderRank':0

        #  'broadcasterId':30008392,
        #  'broadcastId':'206865031',
        #  'propsLevel':52,
        #  'textStyle':0,
        #  'target':0,
    }

    @staticmethod
    def _parse_item(item):

        info = r.remap_dict(item, YouNowChatDownloader._REMAPPING)

        BaseChatDownloader._move_to_dict(info, 'author')

        return info

    def _get_chat_by_user(self, match, params):
        match_id = match.group('id')
        return self.get_chat_by_user_id(match_id, params)

    def _try_get_user_page_info(self, user_id, params):
        url = self._API_TEMPLATE.format(user_id)

        max_attempts = params.get('max_attempts')
        retry_timeout = params.get('retry_timeout')

        for attempt_number in attempts(max_attempts):
            try:
                return self._session_get_json(url)
                break
            except (JSONDecodeError, RequestException) as e:
                self.retry(attempt_number, max_attempts, e, retry_timeout)
        return None

    def get_chat_by_user_id(self, user_id, params):

        initial_info = self._try_get_user_page_info(user_id, params)

        title = initial_info.get('title')

        start_time = initial_info.get('dateStarted')

        chat_item = Chat(is_live=True)  # Create empty chat object
        chat_item.chat = self._get_chat_messages_by_user(
            user_id, chat_item, initial_info, params)

        return chat_item

    _API_TEMPLATE = 'https://api.younow.com/php/api/broadcast/info/curId=0/user={}'

    def _get_chat_messages_by_user(self, user_id, chat_item, initial_info, params):

        # Add initial info comments

        first_time = True

        last_timestamp = 0

        # YouNow does not ID their messages, so we must manually
        # keep a small buffer from the last request
        buffer = []

        while True:
            if first_time:
                # Update stream info on first time
                info = initial_info

                first_time = False
            else:
                info = self._try_get_user_page_info(user_id, params)

            # Check for errors
            error = info.get('errorMsg')
            if error:
                raise YouNowError(error)

            # Clear cookies from previous request
            self.clear_cookies()

            for comment in info.get('comments') or []:
                current_timestamp = comment.get('timestamp')
                if current_timestamp < last_timestamp:
                    continue  # Already processed

                data = self._parse_item(comment)

                author_id = multi_get(data, 'author', 'id')
                message = data.get('message')

                # use author ID and message to generate an ID
                message_hash = hashlib.md5('{} | {}'.format(
                    author_id, message).encode()).hexdigest()

                if current_timestamp > last_timestamp:
                    last_timestamp = current_timestamp
                    buffer = [message_hash]

                else:  # current_timestamp == last_timestamp
                    # same timestamp as before, check if must add

                    if message_hash in buffer:
                        continue  # Already processed

                    # add to buffer
                    buffer.append(message_hash)

                yield data

            # TODO
            # Continuously update title and other metadata (like view counts)
            # chat_item.title = info.get('title')

            interruptible_sleep(1)
