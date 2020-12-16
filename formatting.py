"""
Formatting module.

Provides formatting for chat text output.
"""
from string import Template
import datetime


class ItemFormatter:
    """Formats items according to template."""

    def __init__(self, template, **template_parts):
        """
        Creates item formatter from template and parts.

        Template parts are:
        - timestamp - datetime format for items with timestamp
        - badges - badges in chat item
        - amount - donation amount
        - author - author of chat item
        - message - message of chat item

        :param template: string with $id or/and ${id}
        :param template_parts: dict of parts
        """
        self.template = Template(template)
        self.template_parts = template_parts

    def format(self, item):
        """
        Format given item according to template and parts.

        If part is not in item, replaces it with empty string.
        """
        return self.template.substitute(
            time=self._format_time(item),
            badges=self._format_part(item, 'badges'),
            amount=self._format_part(item, 'amount'),
            author=self._format_part(item, 'author'),
            message=self._format_part(item, 'message')
        )

    def _format_time(self, item):
        """Format time if `timestamp`, leave it if `time_text`."""
        if 'time_text' in item:
            return item['time_text']
        elif 'timestamp' in item:
            parsed_timestamp = self._parse_timestamp(item['timestamp'])
            formatted_timestamp = parsed_timestamp.strftime(
                self.template_parts['timestamp']
            )
            return formatted_timestamp
        else:
            return ''

    @staticmethod
    def _parse_timestamp(timestamp):
        """Parse unix timestamp from item."""
        return datetime.datetime.fromtimestamp(timestamp // 1000000)

    def _format_part(self, item, part):
        """Format part if present in item."""
        if part in item:
            return self.template_parts[part].format(item[part])
        else:
            return ''
