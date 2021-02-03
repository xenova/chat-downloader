"""Lists the sites that are supported"""

from .youtube import YouTubeChatDownloader
from .twitch import TwitchChatDownloader
from .facebook import FacebookChatDownloader
from .common import BaseChatDownloader


def get_all_sites(include_parent=False):
    return [
        value
        for value in globals().values()
        # not the base class
        if isinstance(value, type) and issubclass(value, BaseChatDownloader) and (include_parent or value != BaseChatDownloader)
    ]
