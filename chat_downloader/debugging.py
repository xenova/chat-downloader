"""Debugging module for chat_downloader"""

import sys
import os
import chat_downloader


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
        # Windows Terminal supports VT codes.
        # Microsoft Visual Studio Code's built-in terminal supports colours.

        (sys.platform != 'win32') or ('ANSICON' in os.environ) or ('WT_SESSION' in os.environ) or (
            os.environ.get('TERM_PROGRAM') == 'vscode') or (vt_codes_enabled_in_windows_registry())
    )


if supports_colour():
    import colorlog
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        '[%(log_color)s%(levelname)s%(reset)s] %(message)s',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        })
    )
    log_module = colorlog

else:  # fallback support
    import logging
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    log_module = logging

# Create logger object for this module
logger_name = chat_downloader.__name__
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


def log(level, items, to_pause=False):
    logger_at_level = getattr(logger, level, None)
    if logger_at_level:
        if not isinstance(items, (tuple, list)):
            items = [items]
        for item in items:
            logger_at_level(item)

        if to_pause:
            input('Press Enter to continue...')
