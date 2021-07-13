"""File for defining errors"""


class ChatDownloaderError(Exception):
    """Base class for Chat Downloader errors."""


class UnexpectedError(ChatDownloaderError):
    """Raised if something unexpected happens."""

    def __init__(self, items):
        super().__init__(str(items))


class InvalidParameter(ChatDownloaderError):
    """Raised if an invalid parameter is specified."""
    pass


class RetriesExceeded(ChatDownloaderError):
    """Raised after the maximum number of retries has been reached."""
    pass


class VideoNotFound(ChatDownloaderError):
    """Raised when video cannot be found."""
    pass


class UserNotFound(ChatDownloaderError):
    """Raised when user cannot be found."""
    pass


class NoVideos(ChatDownloaderError):
    """Raised when a channel does not have any videos."""
    pass


class ParsingError(ChatDownloaderError):
    """Raised when video data cannot be parsed."""
    pass


class VideoUnavailable(ChatDownloaderError):
    """Raised when video is unavailable."""
    pass


class LoginRequired(ChatDownloaderError):
    """Raised when video is login is required (e.g. if video is private)."""
    pass


class VideoUnplayable(ChatDownloaderError):
    """Raised when video is unplayable (e.g. if video is members-only)."""
    pass


class NoChatReplay(ChatDownloaderError):
    """Raised when the video does not contain a chat replay."""
    pass


class ChatDisabled(ChatDownloaderError):
    """Raised when the chat is disabled."""
    pass


class URLNotProvided(ChatDownloaderError):
    """Raised when no url is provided."""
    pass


class InvalidURL(ChatDownloaderError):
    """Raised when the url is invalid."""
    pass


class ChatGeneratorError(ChatDownloaderError):
    """Raised when no valid generator method for a site can be found."""
    pass


class SiteError(ChatDownloaderError):
    """Raised when an error occurs with a specific site."""
    pass


class SiteNotSupported(SiteError):
    """Raised when the url is valid, but the site is not supported."""
    pass


class NoContinuation(ChatDownloaderError):
    """Raised when no continuation can be found."""
    pass


class CookieError(ChatDownloaderError):
    """Raised when an error occurs while loading a cookie file."""
    pass


class FormatError(ChatDownloaderError):
    """Raised when a formatting error occurs"""
    pass


class FormatNotFound(FormatError):
    """Raised when a specified format can not be found"""
    pass


class FormatFileNotFound(FormatError):
    """Raised when the format file can not be found"""
    pass
