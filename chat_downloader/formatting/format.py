import re
import os
import json

from ..utils import (
    nested_update,
    multi_get,
    microseconds_to_timestamp
)
from copy import deepcopy


class ItemFormatter:

    _INDEX_REGEX = r'(?<!\\){(.+?)(?<!\\)}'

    # 'always_show': True (default False)

    def __init__(self, path=None):

        if path is None or not os.path.exists(path):
            path = os.path.join(os.path.dirname(
                os.path.realpath(__file__)), 'custom_formats.json')

        with open(path) as custom_formats:
            self.format_file = json.load(custom_formats)

    def replace(self, result, item, format_object):
        split = result.group(1).split('|')

        for index in split:
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
                                value = separator.join(
                                    map(lambda x: str(x), value))
                            else:
                                pass
                    else:
                        pass

                    return template.format(value)

                else:
                    return str(value)

        return ''  # no match, return empty

    def format(self, item, format_name='default', format_object=None):
        default_format_object = self.format_file.get('default')
        if format_object is None:
            format_object = self.format_file.get(
                format_name, default_format_object)

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

        inherit = format_object.get('inherit')
        if inherit:
            parent = self.format_file.get(inherit) or {}
            format_object = nested_update(deepcopy(parent), format_object)

        # print('after',format_object)
        template = format_object.get('template') or ''
        keys = format_object.get('keys') or {}

        substitution = re.sub(self._INDEX_REGEX, lambda result: self.replace(
            result, item, keys), template)

        return substitution
