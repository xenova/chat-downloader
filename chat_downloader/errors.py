"""File for defining errors"""


class UnexpectedError(Exception):
    """Raised if something unexpected happens."""

    def __init__(self, items):
        super().__init__(str(items))


class InvalidParameter(Exception):
    """Raised if an invalid parameter is specified."""
    pass


class RetriesExceeded(Exception):
    """Raised after the maximum number of retries has been reached."""
    pass


class VideoNotFound(Exception):
    """Raised when video cannot be found."""
    pass


class ParsingError(Exception):
    """Raised when video data cannot be parsed."""
    pass


class VideoUnavailable(Exception):
    """Raised when video is unavailable."""
    pass


class LoginRequired(Exception):
    """Raised when video is login is required (e.g. if video is private)."""
    pass


class VideoUnplayable(Exception):
    """Raised when video is unplayable (e.g. if video is members-only)."""
    pass


class NoChatReplay(Exception):
    """Raised when the video does not contain a chat replay."""
    pass


class URLNotProvided(Exception):
    """Raised when no url is provided."""
    pass


class InvalidURL(Exception):
    """Raised when the url is invalid."""
    pass


class SiteNotSupported(Exception):
    """Raised when the url is valid, but the site is not supported."""
    pass


class TwitchError(Exception):
    """Raised when an error occurs with a Twitch video."""
    pass


class NoContinuation(Exception):
    """Raised when no continuation can be found."""
    pass


class CookieError(Exception):
    """Raised when an error occurs while loading a cookie file."""
    pass
