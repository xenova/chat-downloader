"""Debugging module for chat_downloader"""

import sys
import os

from .metadata import __name__ as logger_name
from .utils.core import pause

from enum import Enum


class TestingException(Exception):
    """Raised when something unexpected happens while in testing mode"""


class TestingModes(Enum):
    # Currently unused
    EXIT_ON_ERROR = 4
    PAUSE_ON_ERROR = 3

    # In use
    EXIT_ON_DEBUG = 2
    PAUSE_ON_DEBUG = 1
    NONE = 0


TESTING_MODE = TestingModes.NONE


def set_testing_mode(new_mode):
    global TESTING_MODE
    TESTING_MODE = new_mode


def log(level, items, to_pause=False, to_exit=False):
    logger_at_level = getattr(logger, level, None)
    if logger_at_level:
        if not isinstance(items, (tuple, list)):
            items = [items]
        for item in items:
            logger_at_level(item)

        if to_exit and TESTING_MODE in (TestingModes.EXIT_ON_ERROR, TestingModes.EXIT_ON_DEBUG):
            raise TestingException(
                'Testing exception encountered, exiting program')

        if to_pause and TESTING_MODE in (TestingModes.PAUSE_ON_ERROR, TestingModes.PAUSE_ON_DEBUG):
            pause()


def debug_log(*items):
    """Method which simplifies the logging of debugging messages"""
    log('debug', items, True, True)


try:
    import colorama
    colorama.init()
except (ImportError, OSError):
    HAS_COLORAMA = False
else:
    HAS_COLORAMA = True


def supports_colour():
    """
    Return True if the running system's terminal supports colour,
    and False otherwise.

    Adapted from https://github.com/django/django/blob/master/django/core/management/color.py
    """
    def vt_codes_enabled_in_windows_registry():
        """
        Check the Windows Registry to see if VT code handling has been enabled
        by default, see https://superuser.com/a/1300251/447564.
        """
        try:
            # winreg is only available on Windows.
            import winreg
        except ImportError:
            return False
        else:
            reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Console')
            try:
                reg_key_value, _ = winreg.QueryValueEx(
                    reg_key, 'VirtualTerminalLevel')
            except FileNotFoundError:
                return False
            else:
                return reg_key_value == 1

    # isatty is not always implemented, #6223.
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

    return is_a_tty and (
        sys.platform != 'win32' or
        HAS_COLORAMA or
        'ANSICON' in os.environ or

        # Windows Terminal supports VT codes.
        'WT_SESSION' in os.environ or

        # Microsoft Visual Studio Code's built-in terminal supports colors.
        os.environ.get('TERM_PROGRAM') == 'vscode' or
        vt_codes_enabled_in_windows_registry()
    )


if supports_colour():
    import colorlog as log_module
    handler = log_module.StreamHandler()
    handler.setFormatter(log_module.ColoredFormatter(
        '[%(log_color)s%(levelname)s%(reset)s] %(message)s',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        })
    )

else:  # fallback support
    import logging as log_module
    handler = log_module.StreamHandler()
    handler.setFormatter(log_module.Formatter('[%(levelname)s] %(message)s'))

# Create logger object for this module
logger = log_module.getLogger(logger_name)

# Define which loggers to display
loggers = [log_module.getLogger(name) for name in (logger_name, 'urllib3')]
for logger in loggers:
    logger.addHandler(handler)


def set_log_level(level):
    level_name = level.upper()
    for logger in loggers:
        logger.setLevel(level_name)


def disable_logger():
    logger.disabled = True
