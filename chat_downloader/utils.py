import inspect
import threading
import _thread
import datetime
import re
import sys
import locale
import collections.abc
import io
import time
import json


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


def seconds_to_time(seconds):
    """Convert seconds to timestamp. Note that leading zeroes are omitted
        when seconds > 60

    :param seconds: Number of seconds
    :type seconds: int
    :return: The corresponding timestamp string
    :rtype: str
    """
    h, remainder = divmod(abs(seconds), 3600)
    m, s = divmod(remainder, 60)
    time_string = '{}:{:02}:{:02}'.format(int(h), int(m), int(s))
    return ('-' if s < 0 else '') + re.sub(r'^0:0?', '', str(time_string))


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
    if time is None:  # if time is none, return default
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
            d[k] = nested_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def pause(text='Press Enter to continue...'):
    input(text)

# Inspired by https://github.com/hero24/TimedInput/


class TimedInput(threading.Thread):
    """ Timed input reader """

    def get_input(self):
        """ Actual function for reading the input """
        try:
            print(self.prompt, end='', flush=True)
            self.input = input()
        except EOFError:
            pass

    def __init__(self, timeout, prompt='', default=None, *args, **kwargs):
        """
        TimedInput(
            timeout -> amount of seconds to wait for the input,
            prompt -> optionl prompt to display while asking for input,
            default -> string to return in case of timeout,
            *args/**kwargs -> any additional arguments are passed down to Thread
                            constructor
        )
        Creates an object for reading input, that times out after `timeout` amount
                of seconds.
        """
        self.timeout = timeout
        self.prompt = prompt
        self.input = default
        super().__init__(target=self.get_input, *args, **kwargs)
        self.daemon = True

    def join(self):
        """ The actual timeout happens here """
        super().join(self.timeout)
        return self.input

    def read(self):
        """ Reads the input from the reader """
        self.start()
        return self.join()


class TimedGenerator:
    """
    Add timing functionality to generator objects.

    Used to create timed-generator objects as well as add inactivity functionality
    (i.e. return if no items have been generated in a given time period)
    """

    def __init__(self, generator, timeout=None, inactivity_timeout=None, on_timeout=None, on_inactivity_timeout=None):
        self.generator = generator
        self.timeout = timeout
        self.inactivity_timeout = inactivity_timeout

        self.on_timeout = on_timeout
        self.on_inactivity_timeout = on_inactivity_timeout

        self.timer = self.inactivity_timer = None

        if self.timeout is not None:
            self.start_timer()

        if self.inactivity_timeout is not None:
            self.start_inactivity_timer()

    def start_timer(self):
        self.timer = threading.Timer(self.timeout, _thread.interrupt_main)
        self.timer.start()

    def start_inactivity_timer(self):
        self.inactivity_timer = threading.Timer(
            self.inactivity_timeout, _thread.interrupt_main)
        self.inactivity_timer.start()

    def reset_inactivity_timer(self):
        if self.inactivity_timer:
            self.inactivity_timer.cancel()
            self.start_inactivity_timer()

    def __iter__(self):
        return self

    def __next__(self):
        to_raise = None
        set_timers = [timer for timer in (
            self.timer, self.inactivity_timer) if timer is not None]

        try:
            next_item = next(self.generator)
            self.reset_inactivity_timer()
            return next_item

        except KeyboardInterrupt as e:

            if not set_timers:
                # Neither timer has been set, so we treat this
                # as a normal KeyboardInterrupt. No need to cancel
                # timers afterwards, we can exit here.
                raise e

            # get expired timers
            expired_timers = [
                timer for timer in set_timers if not timer.is_alive()]
            if expired_timers:
                # Some timer expired
                first_expired = expired_timers[0]

                to_raise = StopIteration
                function = self.on_timeout if (
                    first_expired == self.timer) else self.on_inactivity_timeout
                self._run_function(function)

            else:  # both timers are still active, user sent a keyboard interrupt
                to_raise = e

        except Exception as e:
            # Some other error. Always propogate.
            # If e is StopIteration, there are no more items to get.
            # We can close the timers before exiting
            to_raise = e

        if to_raise:  # Something happened which will cause the generator to exit, cancel timers
            for timer in set_timers:
                timer.cancel()

            raise to_raise

    def _run_function(self, function):
        if callable(function):
            function()


def timed_input(timeout=None, prompt='', default=None, *args, **kwargs):
    if timeout is None:
        return input(prompt)
    else:
        return TimedInput(timeout, prompt, default, *args, **kwargs).read()


def interruptible_sleep(secs, poll_time=0.1):
    start_time = time.time()

    while time.time() - start_time <= secs:
        time.sleep(poll_time)


def get_default_args(func):
    signature = inspect.signature(func)
    return {
        k: v.default
        for k, v in signature.parameters.items()
        if v.default is not inspect.Parameter.empty
    }
