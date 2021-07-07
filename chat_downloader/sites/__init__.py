"""Lists the sites that are supported"""

from .youtube import YouTubeChatDownloader
from .twitch import TwitchChatDownloader
from .facebook import FacebookChatDownloader
from .reddit import RedditChatDownloader
from .common import BaseChatDownloader


def get_all_sites(include_parent=False):
    """Get all supported sites.

    :param include_parent: Whether to include the BaseChatDownloader, defaults to False
    :type include_parent: bool, optional
    :return: A list of all supported ChatDownloader classes
    :rtype: list
    """
    return [
        value
        for value in globals().values()
        # not the base class
        if isinstance(value, type) and issubclass(value, BaseChatDownloader) and (include_parent or value != BaseChatDownloader)
    ]
