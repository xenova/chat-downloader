import inspect
import datetime
import re
import sys
import locale
import collections.abc
import io
import json


def splitter(s):
    return [item.strip() for item in re.split(r'[\s,;]+', s)]


def timestamp_to_microseconds(timestamp):
    """Convert RFC3339 timestamp to microseconds. This is needed since
        ``datetime.datetime.strptime()`` does not support nanosecond precision.

    :param timestamp: RFC3339 timestamp
    :type timestamp: str
    :return: The number of microseconds of the timestamp
    :rtype: int
    """

    info = list(filter(None, re.split(r'[\.|Z]{1}', timestamp))) + [0]
    return round((datetime.datetime.strptime('{}Z'.format(info[0]), '%Y-%m-%dT%H:%M:%SZ').timestamp() + float('0.{}'.format(info[1]))) * 1e6)


def time_to_seconds(time):
    """Convert timestamp string of the form 'hh:mm:ss' to seconds.

    :param time: Timestamp of the form 'hh:mm:ss'
    :type time: str
    :return: The corresponding number of seconds
    :rtype: int
    """
    if not time:
        return 0
    return int(sum(abs(int(x)) * 60 ** i for i, x in enumerate(reversed(time.replace(',', '').split(':')))) * (-1 if time[0] == '-' else 1))


def seconds_to_time(seconds, format='{}:{:02}:{:02}', remove_leading_zeroes=True):
    """Convert seconds to timestamp.

    :param seconds: Number of seconds
    :type seconds: int
    :param format: The format string with elements representing hours, minutes and seconds. Defaults to '{}:{:02}:{:02}'
    :type format: str, optional
    :param remove_leading_zeroes: Whether to remove leading zeroes when seconds > 60, defaults to True
    :type remove_leading_zeroes: bool, optional
    :return: The corresponding timestamp string
    :rtype: str
    """
    h, remainder = divmod(abs(int(seconds)), 3600)
    m, s = divmod(remainder, 60)
    time_string = format.format(h, m, s)
    return ('-' if seconds < 0 else '') + re.sub(r'^0:0?', '', time_string) if remove_leading_zeroes else time_string


def microseconds_to_timestamp(microseconds, format='%Y-%m-%d %H:%M:%S'):
    """Convert unix time to human-readable timestamp.

    :param microseconds: UNIX microseconds
    :type microseconds: float
    :param format: The format string, defaults to '%Y-%m-%d %H:%M:%S'. For
        information on supported codes, see https://strftime.org/ and
        https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
    :type format: str, optional
    :return: Human readable timestamp corresponding to the format
    :rtype: str
    """
    return datetime.datetime.fromtimestamp(microseconds // 1000000).strftime(format)


def ensure_seconds(time, default=None):
    """Ensure time is returned in seconds.

    :param time: The time, in seconds or 'hh:mm:ss'.
    :type time: Union[float, str]
    :param default: Returns this if unable to parse the time, defaults to None
    :type default: object, optional
    :return: The corresponding number of seconds
    :rtype: float
    """
    if time is None:
        return default

    try:
        return float(time)
    except ValueError:
        return time_to_seconds(time)
    except Exception:
        return default


def arbg_int_to_rgba(argb_int):
    """Convert ARGB integer to RGBA array.

    :param argb_int: ARGB integer
    :type argb_int: int
    :return: RGBA array
    :rtype: list[int]
    """
    red = (argb_int >> 16) & 255
    green = (argb_int >> 8) & 255
    blue = argb_int & 255
    alpha = (argb_int >> 24) & 255
    return [red, green, blue, alpha]


def rgba_to_hex(colours):
    """Convert RGBA array to hex colour.

    :param colours: RGBA array
    :type colours: list[int]
    :return: Corresponding hexadecimal representation
    :rtype: str
    """
    return '#{:02x}{:02x}{:02x}{:02x}'.format(*colours)


# from youtube-dl
def try_get(src, getter, expected_type=None):
    # used when a method is needed
    # or list/number index retrieval
    for get in wrap_as_list(getter):
        try:
            v = get(src)
        except (AttributeError, KeyError, TypeError, IndexError):
            pass
        else:
            if expected_type is None or isinstance(v, expected_type):
                return v


def get_title_of_webpage(html):
    match = re.search('<title(?:[^>]*)>(.*?)</title>', html)
    return match.group(1) if match else None


def int_or_none(v, default=None):
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def float_or_none(v, default=None):
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def str_or_none(v, default=None):
    try:
        return str(v)
    except (ValueError, TypeError):
        return default


def try_get_first_key(dictionary, default=None):
    try:
        return next(iter(dictionary))
    except Exception:
        return default


def try_get_first_value(dictionary, default=None):
    try:
        return next(iter(dictionary.values()))
    except Exception:
        return default


def try_parse_json(text):
    try:
        return json.loads(text)
    except json.decoder.JSONDecodeError:
        return None


def wrap_as_list(item):
    """Wraps an item in a list, if it is not already iterable

    :param item: The item to wrap
    :type item: object
    :return: The wrapped item
    :rtype: Union[list, tuple]
    """
    if not isinstance(item, (list, tuple)):
        item = [item]
    return item


def remove_prefixes(text, prefixes):
    for prefix in wrap_as_list(prefixes):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text


def remove_suffixes(text, suffixes):
    for suffix in wrap_as_list(suffixes):
        if text.endswith(suffix):
            text = text[0:-len(suffix):]
    return text


def update_dict_without_overwrite(original, new):
    original.update({key: new[key] for key in new if key not in original})
    return original


def camel_case_split(word):
    return '_'.join(re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', word)).lower()


def replace_with_underscores(text, sep='-'):
    return text.replace(sep, '_')


def multi_get(dictionary, *keys, default=None):
    current = dictionary
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        elif isinstance(current, (list, tuple)) and isinstance(key, int) and key < len(current):
            current = current[key]
        else:
            return default
    return current


def flatten_json(original_json):
    final = {}

    def flatten(item, prefix=''):
        if isinstance(item, dict):
            for key in item:
                flatten(item[key], '{}{}.'.format(prefix, key))
        elif isinstance(item, list):
            for index in range(len(item)):
                flatten(item[index], '{}{}.'.format(prefix, index))
        else:
            final[prefix[:-1]] = item
    flatten(original_json)

    return final


def attempts(max_attempts):
    return range(1, max_attempts + 1)


def preferredencoding():
    """Get preferred encoding.
    Returns the best encoding scheme for the system, based on
    locale.getpreferredencoding() and some further tweaks.
    """
    try:
        pref = locale.getpreferredencoding()
        'TEST'.encode(pref)
    except Exception:
        pref = 'utf-8'

    return pref


def _windows_write_string(s, out, skip_errors=True):
    """ Returns True if the string was written using special methods,
    False if it has yet to be written out."""
    # Adapted from http://stackoverflow.com/a/3259271/35070

    import ctypes
    import ctypes.wintypes

    WIN_OUTPUT_IDS = {
        1: -11,
        2: -12,
    }

    try:
        fileno = out.fileno()
    except AttributeError:
        # If the output stream doesn't have a fileno, it's virtual
        return False
    except io.UnsupportedOperation:
        # Some strange Windows pseudo files?
        return False
    if fileno not in WIN_OUTPUT_IDS:
        return False

    GetStdHandle = ctypes.WINFUNCTYPE(
        ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD)(
        ('GetStdHandle', ctypes.windll.kernel32))
    h = GetStdHandle(WIN_OUTPUT_IDS[fileno])

    WriteConsoleW = ctypes.WINFUNCTYPE(
        ctypes.wintypes.BOOL, ctypes.wintypes.HANDLE, ctypes.wintypes.LPWSTR,
        ctypes.wintypes.DWORD, ctypes.POINTER(ctypes.wintypes.DWORD),
        ctypes.wintypes.LPVOID)(('WriteConsoleW', ctypes.windll.kernel32))
    written = ctypes.wintypes.DWORD(0)

    GetFileType = ctypes.WINFUNCTYPE(ctypes.wintypes.DWORD, ctypes.wintypes.DWORD)(
        ('GetFileType', ctypes.windll.kernel32))
    FILE_TYPE_CHAR = 0x0002
    FILE_TYPE_REMOTE = 0x8000
    GetConsoleMode = ctypes.WINFUNCTYPE(
        ctypes.wintypes.BOOL, ctypes.wintypes.HANDLE,
        ctypes.POINTER(ctypes.wintypes.DWORD))(
        ('GetConsoleMode', ctypes.windll.kernel32))
    INVALID_HANDLE_VALUE = ctypes.wintypes.DWORD(-1).value

    def not_a_console(handle):
        if handle == INVALID_HANDLE_VALUE or handle is None:
            return True
        return ((GetFileType(handle) & ~FILE_TYPE_REMOTE) != FILE_TYPE_CHAR or GetConsoleMode(handle, ctypes.byref(ctypes.wintypes.DWORD())) == 0)

    if not_a_console(h):
        return False

    def next_nonbmp_pos(s):
        try:
            return next(i for i, c in enumerate(s) if ord(c) > 0xffff)
        except StopIteration:
            return len(s)

    while s:
        count = min(next_nonbmp_pos(s), 1024)

        ret = WriteConsoleW(
            h, s, count if count else 2, ctypes.byref(written), None)
        if ret == 0:
            if skip_errors:
                continue
            else:
                raise OSError('Failed to write string')
        if not count:  # We just wrote a non-BMP character
            assert written.value == 2
            s = s[1:]
        else:
            assert written.value > 0
            s = s[written.value:]
    return True


def safe_print(*objects, sep=' ', end='\n', out=None, encoding=None, flush=False):
    """
    Ensure printing to standard output can be done safely (especially on Windows).
    There are usually issues with printing emojis and non utf-8 characters.
    """

    output_string = sep.join(map(lambda x: str(x), objects)) + end

    if out is None:
        out = sys.stdout

    if sys.platform == 'win32' and encoding is None and hasattr(out, 'fileno'):
        if _windows_write_string(output_string, out):
            return

    if 'b' in getattr(out, 'mode', '') or not hasattr(out, 'buffer'):
        out.write(output_string)
    else:
        enc = encoding or getattr(out, 'encoding', None) or preferredencoding()
        byt = output_string.encode(enc, 'ignore')
        out.buffer.write(byt)

    if flush and hasattr(out, 'flush'):
        out.flush()


def nested_update(d, u):
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            a = d.get(k, {})
            if isinstance(a, dict):
                d[k] = nested_update(a, v)
            else:
                d[k] = v
        else:
            d[k] = v
    return d


def pause(text='Press Enter to continue...'):
    input(text)


def get_default_args(func):
    signature = inspect.signature(func)
    return {
        k: v.default
        for k, v in signature.parameters.items()
        if v.default is not inspect.Parameter.empty
    }
