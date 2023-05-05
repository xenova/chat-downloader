

import json
import re
from .common import (
    BaseChatDownloader,
    Chat,
    Remapper as r
)
from ..utils.core import (
    time_to_seconds,
    regex_search,
    ensure_seconds,
    multi_get,
)
from ..errors import (
    SiteError,
    ParsingError
)

# TODO add debugging options
# from ..debugging import (
#     log,
#     debug_log
# )


class ZoomError(SiteError):
    """Raised when an error occurs with a Zoom video."""
    pass


class ZoomChatDownloader(BaseChatDownloader):
    _NAME = 'zoom.us'

    _ZOOM_HOMEPAGE = 'https://zoom.us/'
    _ZOOM_PATH_TEMPLATE = 'rec/play/{id}'
    _ZOOM_API_TEMPLATE = 'nws/recording/1.0/play/info/{file_id}'

    _INITIAL_INFO_REGEX = r'(?s)window\.__data__\s*=\s*({.+?});'
    _CHAT_MESSAGES_REGEX = r'window\.__data__\.chatList\.push\((\{[\s\S]+?\})\)'

    _SITE_DEFAULT_PARAMS = {
        'format': 'default',  # TODO create zoom format
    }

    _REMAPPING = {
        'userName': 'author_name',
        'time': 'time_text',
        'content': 'message',
    }

    _TESTS = [
        {
            'name': 'Get chat messages from past broadcast #1',
            'params': {
                'url': 'https://zoom.us/rec/play/6ccrIuigqG83GIaT4wSDAv59W9W5J_-s1HUe_6UPykq3V3hVN1emMucTYLEJiA87rIkEPcGptB0Dp_dH',
                'max_messages': 10
            },
            'expected_result': {
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },
        {
            'name': 'Get chat messages from past broadcast #2',
            'params': {
                'url': 'https://zoom.us/rec/play/65V5deGq-Do3T9bHuASDAv4tW420f_ms1iIb-vIKzEqzUiEFNFWiYONAN-vRvNmKnlg6z95Y4mNQ9QJQ',
                'max_messages': 10
            },
            'expected_result': {
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },
        {
            'name': 'Get chat messages from past broadcast #3',
            'params': {
                'url': 'https://zoom.us/rec/play/75Usc7j8rjg3E92S4gSDAf95W9S9K6-sg3dP_voImR60WiEHYVSmYrsbNwNE1_6-jwlwLx5cg1IeyjM',
                'max_messages': 10
            },
            'expected_result': {
                'messages_condition': lambda messages: len(messages) > 0,
            }
        },
        {
            'name': 'Invalid video',
            'params': {
                'url': 'https://zoom.us/rec/play/invalid',
            },
            'expected_result': {
                'error': ZoomError
            }
        },
    ]

    # Regex provided by youtube-dl
    _VALID_URLS = {
        '_get_chat_by_video_id': r'(?P<base_url>https?://(?:[^.]+\.)?zoom.us/)rec(?:ording)?/(?:play|share)/(?P<id>[A-Za-z0-9_.-]+)',
    }
    _ERROR_MESSAGE_REGEX = r'<span class="error-message">\s*([^<]+?)\s*<\/span>'

    def _get_chat_by_video_id(self, match, params):
        match_id = match.group('id')
        base_url = match.group('base_url')
        return self.get_chat_by_video_id(match_id, params, base_url=base_url)

    def get_chat_by_video_id(self, video_id, params, base_url=_ZOOM_HOMEPAGE):

        url = base_url + self._ZOOM_PATH_TEMPLATE.format(id=video_id)
        page_data = self._session_get(url).text

        json_string = regex_search(page_data, self._INITIAL_INFO_REGEX)

        if json_string is None:
            error_message = regex_search(page_data, self._ERROR_MESSAGE_REGEX)
            if error_message:
                raise ZoomError(error_message.split('\n')[0])
            else:
                raise ParsingError('Error parsing video')

        initial_info = self._parse_js_dict(json_string)
        video_type = 'video' if initial_info.get('isVideo') else 'not_video'

        file_id = initial_info.get('fileId')
        if not file_id:
            raise ParsingError('Error parsing video. Unable to find file ID.')

        api_url = base_url + self._ZOOM_API_TEMPLATE.format(file_id=file_id)

        api_data = self._session_get_json(api_url)

        if api_data.get('errorCode') != 0:
            raise ZoomError(
                f'An error occured: {api_data.get("errorMessage")} ({api_data.get("errorCode")})')

        result = api_data.get('result')
        if not result:
            raise ZoomError(
                f'Unable to find chat messages for video {video_id}')

        chat_messages = result.get('meetingChatList') or []
        title = multi_get(result, 'meet', 'topic')
        return Chat(
            self._get_chat_messages(chat_messages, params),
            title=title,
            video_type=video_type,
            start_time=result.get('fileStartTime'),
            id=video_id,
            duration=result.get('duration'),
        )

    def _parse_js_dict(self, json_string):
        # Helper method to parse JS dictionary format
        result = re.sub(r"^([^:\s]+):\s+", r'"\g<1>": ',
                        json_string, 0, re.MULTILINE)
        result = result.replace(r"\'", "'")
        result = re.sub(r":\s+'(.*)'", ": \"\\g<1>\"", result, 0, re.MULTILINE)
        return json.loads(result)

    def _get_chat_messages(self, messages, params):
        start_time = ensure_seconds(params.get('start_time'), 0)
        end_time = ensure_seconds(params.get('end_time'), float('inf'))

        for data in messages:
            data = r.remap_dict(data, self._REMAPPING)

            # Process time inforamtion
            data['time_in_seconds'] = time_to_seconds(data['time_text'])
            if data['time_in_seconds'] < start_time:
                continue

            if data['time_in_seconds'] > end_time:
                return

            BaseChatDownloader._move_to_dict(data, 'author')
            yield data
