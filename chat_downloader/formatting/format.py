import re
import os
import json

from ..utils.core import (
    nested_update,
    multi_get,
    microseconds_to_timestamp,
    seconds_to_time,
    time_to_seconds
)
from copy import deepcopy


from ..errors import (
    FormatNotFound,
    FormatFileNotFound
)


class ItemFormatter:
    """Class used to control the formatting of chat items."""

    _INDEX_REGEX = r'(?<!\\){(.+?)(?<!\\)}'

    # 'always_show': True (default False)

    def __init__(self, path=None):
        """Create an ItemFormatter object

        :param path: Path of the format file, defaults to None
        :type path: str, optional
        """
        default_path = os.path.join(os.path.dirname(
            os.path.realpath(__file__)), 'custom_formats.json')

        with open(default_path) as default_formats:
            self.format_file = json.load(default_formats)

        if path is not None:
            if not os.path.exists(path):
                raise FormatFileNotFound(
                    'Format file not found: "{}"'.format(path))

            with open(path) as custom_formats:
                self.format_file.update(json.load(custom_formats))

    def _replace(self, match, item, format_object):
        """Replace a match object with

        :param match: The match object
        :type match: re.Match
        :param item: The chat item to choose the value to replace the key with
        :type item: dict
        :param format_object: The format object which defines how the
            replacement should be done
        :type format_object: dict
        :return: The replacement value as a string
        :rtype: str
        """

        split = match.group(1).split('|')

        for index in split:
            value = multi_get(item, *index.split('.'))

            if value is None:
                continue

            formatting_info = format_object.get(index)
            if formatting_info is None:
                return str(value)

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
                    elif index == 'time_text':
                        collapse_leading_zeroes = formatting_info.get(
                            'collapse_leading_zeroes')
                        value = seconds_to_time(time_to_seconds(
                            value), formatting, collapse_leading_zeroes)
                    else:
                        pass   # TODO add others

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

        return ''  # no match, return empty

    def format(self, item, format_name='default', format_object=None):
        """Format a chat item according to a format (specified by its name),
            found in the format_object

        :param item: The chat item to be formatted
        :type item: dict
        :param format_name: The name of the format to be applied, defaults
            to 'default'
        :type format_name: str, optional
        :param format_object: The format object from which the format will
            be chosen, defaults to None
        :type format_object: dict, optional
        :return: The string representation of the chat item
        :rtype: str
        """
        default_format_object = self.format_file.get('default')
        if format_object is None:
            format_object = self.format_file.get(format_name)
            if not format_object:
                if format_name != 'default':
                    raise FormatNotFound(
                        'Format not found: "{}"'.format(format_name))
                else:
                    format_object = default_format_object  # Set to default

        if isinstance(format_object, list):
            does_match = False

            for fmt in format_object:
                matching = fmt.get('matching')
                message_type = item.get('message_type')
                if isinstance(matching, list):
                    does_match = message_type in matching
                else:
                    does_match = matching == 'all' or message_type == matching

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

        template = format_object.get('template') or ''
        keys = format_object.get('keys') or {}

        substitution = re.sub(self._INDEX_REGEX, lambda match: self._replace(
            match, item, keys), template)

        return substitution
