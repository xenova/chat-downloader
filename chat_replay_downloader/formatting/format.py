import re
import datetime
import os
import json

from ..utils import (
    nested_update,
    multi_get
)

# TODO remove and use utils


def microseconds_to_timestamp(microseconds, format='%Y-%m-%d %H:%M:%S'):
    """Convert unix time to human-readable timestamp."""
    return datetime.datetime.fromtimestamp(microseconds//1000000).strftime(format)


class ItemFormatter:

    _INDEX_REGEX = r'(?<!\\){(.+?)(?<!\\)}'

# 'always_show': True (default False)

    def __init__(self, path=None):

        if path is None or not os.path.exists(path):
            path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'custom_formats.json')

        with open(path) as custom_formats:
            self.format_file = json.load(custom_formats)

    def replace(self, result, item, format_object):
        #print(format_object.keys(), item)
        # print()
        # split by | not enclosed in []
        # split = result.split('|') #re.split(, result.group(2))
        split = result.group(1).split('|')
        # print(split)
        for index in split:
            # print(index.split('.'))
            value = multi_get(item, *index.split('.'))

            if value is not None:

                formatting_info = format_object.get(index)
                if formatting_info is not None:
                    template = ''
                    if isinstance(formatting_info, str):
                        template = formatting_info
                    elif isinstance(formatting_info, dict):
                        template = formatting_info.get('template') or ''

                        formatting = formatting_info.get('format')
                        if formatting:
                            if index == 'timestamp':
                                value = microseconds_to_timestamp(
                                    value, formatting)
                            elif index == '...':
                                pass

                        # Apply separator
                        separator = formatting_info.get('separator')
                        if separator:
                            if index == 'author.badges':
                                value = separator.join(
                                    map(lambda key: key.get('title'), value))
                            elif isinstance(value, (tuple, list)):
                                value = separator.join(map(lambda x: str(x),value))
                            else:
                                pass
                    else:
                        pass

                    return template.format(value)

                else:
                    return str(value)

        return ''  # no match, return empty

    def format(self, item, format_name='default', format_object=None):
        default_format_object = self.format_file.get(format_name, self.format_file.get('default'))
        if format_object is None:
            format_object = default_format_object

        if isinstance(format_object, list):
            does_match = False

            for fmt in format_object:
                matching = fmt.get('matching')
                message_type = item.get('message_type')
                if isinstance(matching, list):
                    does_match = message_type in matching
                elif matching == 'all':
                    does_match = True
                else:
                    does_match = message_type == matching

                if does_match:
                    format_object = fmt
                    break

            if not does_match:
                format_object = default_format_object
            # format_object = next((x for x in format_object if item.get(
            #     'message_type') in x.get('matching') or x.get('matching') == 'all'), None)

        if not format_object:
            return  # raise no format given

        # print('before',format_object)
        inherit = format_object.get('inherit')
        if inherit:
            parent = self.format_file.get(inherit) or {}
            # print('parent',parent)
            format_object = nested_update(parent, format_object)


        # print('after',format_object)
        template = format_object.get('template') or ''
        keys = format_object.get('keys') or {}

        substitution = re.sub(self._INDEX_REGEX, lambda result: self.replace(
            result, item, keys), template)

        return substitution
        # empty_substitution = re.sub(self._INDEX_REGEX, '', template)
        # #print(substitution, empty_substitution)
        # # returns (new, num_modifications)
        # if substitution != empty_substitution:  # some substitution made
        #     return substitution
        # else:
        #     return None


# TODO make formatting e.g. author.name

item1 = {
    "action_type": "text_message",
    "author_badges": [
        {
            "badge_id": "5d9f2208-5dd8-11e7-8513-2ff4adfae661",
            "click_action": "subscribe_to_channel",
            "click_url": "",
            "description": "1-Month Subscriber",
            "icons": [
                {
                        "height": 18,
                        "id": "18x18",
                        "url": "https://static-cdn.jtvnw.net/badges/v1/5d9f2208-5dd8-11e7-8513-2ff4adfae661/1",
                        "width": 18
                },
                {
                    "height": 36,
                    "id": "36x36",
                    "url": "https://static-cdn.jtvnw.net/badges/v1/5d9f2208-5dd8-11e7-8513-2ff4adfae661/2",
                    "width": 36
                },
                {
                    "height": 72,
                    "id": "72x72",
                    "url": "https://static-cdn.jtvnw.net/badges/v1/5d9f2208-5dd8-11e7-8513-2ff4adfae661/3",
                    "width": 72
                }
            ],
            "months": 1,
            "title": "1-Month Subscriber",
            "type": "subscriber",
            "version": 0
        }
    ],
    "author_display_name": "pr0faka",
    "author_id": "545470622",
    "author_name": "pr0faka",
    "channel_id": "151283108",
    "colour": "#008000",
    "is_moderator": False,
    "message": "people born in 1988 have a bad time picking user names",
    "message_id": "ac48cdd8-af9b-4d4a-be5a-7eaaacbd212a",
    "message_type": "text_message",
    "timestamp": 1608220470845000
}
item2 = {
    "action_type": "add_chat_item",
    "author_badges": [
        {
            "icons": [
                {
                    "height": 16,
                    "id": "16x16",
                    "url": "https://yt3.ggpht.com/7Y0B8yW1lfXCmMR5JR5pmney6UxJPBdL--4QgVqVKlPcMr-i0IF2Y74ghx3lhIkDzuybfRTQWA=s16-c-k",
                    "width": 16
                },
                {
                    "height": 32,
                    "id": "32x32",
                    "url": "https://yt3.ggpht.com/7Y0B8yW1lfXCmMR5JR5pmney6UxJPBdL--4QgVqVKlPcMr-i0IF2Y74ghx3lhIkDzuybfRTQWA=s32-c-k",
                    "width": 32
                },
                {
                    "id": "source",
                    "url": "https://yt3.ggpht.com/7Y0B8yW1lfXCmMR5JR5pmney6UxJPBdL--4QgVqVKlPcMr-i0IF2Y74ghx3lhIkDzuybfRTQWA"
                }
            ],
            "title": "Member (2 months)"
        }
    ],
    "author_id": "UCjGX7N9LQNwTYvXFGyxwS2w",
    "author_images": [
        {
            "height": 32,
            "url": "https://yt3.ggpht.com/ytc/AAUvwnjuAJvUDBEYFogGefU7LcpeQvih0KAXamHdj35hBw=s32-c-k-c0xffffffff-no-rj-mo",
            "width": 32
        },
        {
            "height": 64,
            "url": "https://yt3.ggpht.com/ytc/AAUvwnjuAJvUDBEYFogGefU7LcpeQvih0KAXamHdj35hBw=s64-c-k-c0xffffffff-no-rj-mo",
            "width": 64
        }
    ],
    "author_name": "Sophia Sokolova",
    "message": "6 minutes :_raeHype:",
    "message_id": "CjkKGkNKeVd6SnJleS0wQ0ZiSGtnZ29kWWJ3T29nEhtDSmpCaDdIY3ktMENGUnJmVlFvZGRBOEFpdzc%3D",
    "message_type": "text_message",
    "time_in_seconds": -76,
    "time_text": "-1:16",
    "timestamp": 1607889245637404
}
# formatter = ItemFormatter()

# formatted = formatter.format(item2)
# print(formatted)
