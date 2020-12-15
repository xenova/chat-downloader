import re
import datetime
# from ..utils import (
#     microseconds_to_timestamp
# )

# TODO remove and use utils
def microseconds_to_timestamp(microseconds, format='%Y-%m-%d %H:%M:%S'):
    """Convert unix time to human-readable timestamp."""
    return datetime.datetime.fromtimestamp(microseconds//1000000).strftime(format)

class ItemFormatter:

    _INDEX_REGEX = r'(?<!\\){(.+?)(?<!\\)}'
    _DEFAULT_FORMAT = {
        # 'normal': {
        'text_message': {
            'template': '{time_text|timestamp} {badges} {author_name}: {message}',
            'keys': {
                'time_text': {
                    'prefix': '[',
                    'suffix': ']',
                    # 'hide_on_empty': False (default True)
                },
                'timestamp': {
                    'prefix': '[',
                    'format': '%Y-%m-%d %H:%M:%S',
                    'suffix': ']'
                },
                'badges': {
                    'prefix': '(',
                    # 'function':'join',
                    'suffix': ')'
                },
            },
        }
        # }
    }

    def __init__(self):
        pass

    @staticmethod
    def replace(result, item, format_object):
        #print(format_object.keys(), item)
        #print()
        # split by | not enclosed in []
        #split = result.split('|') #re.split(, result.group(2))
        split = result.group(1).split('|')
        #print(split)
        for index in split:
            value = item.get(index)
            formatting = format_object.get(index)
            if value: # found, will return
                if formatting:
                    pass
                    prefix = formatting.get('prefix') or ''
                    f = formatting.get('format')
                    suffix = formatting.get('suffix') or ''

                    if index == 'timestamp' and f:
                        print(value)
                        value = microseconds_to_timestamp(value, f)
                        print(value)
                    #print(formatting)

                    return '{}{}{}'.format(prefix, value, suffix)


                else:
                    return str(value)
                #print(value)




                return ''#value


            #

        return 'q'  # no match, return empty

    @staticmethod
    def format(item, format_object=_DEFAULT_FORMAT):
        #print(format_object, item.get('message_type'))
        message_type_format = format_object.get(item.get('message_type'))
        if not message_type_format:
            return

        #f = format_object.get()
        template = message_type_format.get('template')
        keys = message_type_format.get('keys')

        return re.sub(ItemFormatter._INDEX_REGEX, lambda result: ItemFormatter.replace(result, item, keys), template)

        #q = re.findall(, template)
        #print(q)
        #return 'a'
        # _INDEX_REGEX


item = {
    "action_type": "text_message",
    "author_badges": [
        {
            "description": "12-Month Subscriber",
            "months": 12,
            "title": "12-Month Subscriber",
            "type": "subscriber",
            "version": 12
        },
        {
            "badge_id": "ca980da1-3639-48a6-95a3-a03b002eb0e5",
            "click_action": "visit_url",
            "click_url": "https://www.twitch.tv/overwatchleague",
            "description": "OWL All-Access Pass 2019",
            "image_url_1x": "https://static-cdn.jtvnw.net/badges/v1/ca980da1-3639-48a6-95a3-a03b002eb0e5/1",
            "image_url_2x": "https://static-cdn.jtvnw.net/badges/v1/ca980da1-3639-48a6-95a3-a03b002eb0e5/2",
            "image_url_4x": "https://static-cdn.jtvnw.net/badges/v1/ca980da1-3639-48a6-95a3-a03b002eb0e5/3",
            "title": "OWL All-Access Pass 2019",
            "type": "overwatch_league_insider_2019A",
            "version": 1
        }
    ],
    "author_display_name": "OLUWAKANYINSOLAALBINO",
    "author_id": "430600257",
    "author_name": "oluwakanyinsolaalbino",
    "channel_id": "71190292",
    "colour": "#00FFFB",
    "is_moderator": False,
    "message": "VeryPog",
    "message_id": "401ebf19-22c8-4a72-a3fe-a60d4b399aed",
    "message_type": "text_message",
    "timestamp": 1607999278938000
}

formatted = ItemFormatter.format(item)
print(formatted)
