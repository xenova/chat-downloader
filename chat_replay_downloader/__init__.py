"""Top-level package for chat-replay-downloader."""

__author__ = 'Joshua Lochner'
__email__ = 'admin@xenova.com'
__version__ = '0.0.5'
__url__ = 'https://github.com/xenova/chat_replay_downloader'

from .cli import main

from .chat_replay_downloader import ChatDownloader
import chat_replay_downloader.sites
