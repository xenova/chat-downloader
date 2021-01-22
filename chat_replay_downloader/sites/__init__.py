"""Lists the sites that are supported"""

from .youtube import YouTubeChatDownloader
from .twitch import TwitchChatDownloader
from .facebook import FacebookChatDownloader

from .common import ChatDownloader

def get_all_sites():
    return [
        value
        for value in globals().values()
        if isinstance(value, type) and issubclass(value,ChatDownloader)
        and value != ChatDownloader # not the base class
    ]
