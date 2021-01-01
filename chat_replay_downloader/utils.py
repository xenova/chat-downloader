import datetime
import re
import sys
import emoji


def timestamp_to_microseconds(timestamp):
    """
    Convert RFC3339 timestamp to microseconds.
    This is needed as datetime.datetime.strptime() does not support nanosecond precision.
    """
    info = list(filter(None, re.split('[\.|Z]{1}', timestamp))) + [0]
    return round((datetime.datetime.strptime('{}Z'.format(info[0]), '%Y-%m-%dT%H:%M:%SZ').timestamp() + float('0.{}'.format(info[1])))*1e6)


def time_to_seconds(time):
    """Convert timestamp string of the form 'hh:mm:ss' to seconds."""
    return int(sum(abs(int(x)) * 60 ** i for i, x in enumerate(reversed(time.replace(',', '').split(':')))) * (-1 if time[0] == '-' else 1))


def seconds_to_time(seconds):
    """Convert seconds to timestamp."""
    return ('-' if seconds < 0 else '') + re.sub(r'^0:0?', '', str(datetime.timedelta(0, abs(seconds))))


def microseconds_to_timestamp(microseconds, format='%Y-%m-%d %H:%M:%S'):
    """Convert unix time to human-readable timestamp."""
    return datetime.datetime.fromtimestamp(microseconds//1000000).strftime(format)

def ensure_seconds(time, default=None):
    """Ensure time is returned in seconds."""
    if(not time):  # if empty, return default
        return default

    try:
        return int(time)
    except ValueError:
        return time_to_seconds(time)
    except:
        return default


def arbg_int_to_rgba(argb_int):
    """Convert ARGB integer to RGBA array."""
    red = (argb_int >> 16) & 255
    green = (argb_int >> 8) & 255
    blue = argb_int & 255
    alpha = (argb_int >> 24) & 255
    return [red, green, blue, alpha]


def rgba_to_hex(colours):
    """Convert RGBA array to hex colour."""
    return '#{:02x}{:02x}{:02x}{:02x}'.format(*colours)


def get_colours(argb_int):
    """Given an ARGB integer, return both RGBA and hex values."""
    rgba_colour = arbg_int_to_rgba(argb_int)
    hex_colour = rgba_to_hex(rgba_colour)
    return {
        'argb_int': argb_int,
        'rgba': rgba_colour,
        'hex': hex_colour
    }

# from youtube-dl


def try_get(src, getter, expected_type=None):
    # used when a method is needed
    if not isinstance(getter, (list, tuple)):
        getter = [getter]
    for get in getter:
        try:
            v = get(src)
        except (AttributeError, KeyError, TypeError, IndexError):
            pass
        else:
            if expected_type is None or isinstance(v, expected_type):
                return v


def get_title_of_webpage(html):
    match = re.search('<title>(.*?)</title>', html)
    if(match):
        return match.group(1)
    else:
        return None


def int_or_none(v, default=None):
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def try_get_first_key(dictionary, default=None):
    try:
        return next(iter(dictionary))
    except:
        return default

def try_get_first_value(dictionary, default=None):
    try:
        return next(iter(dictionary.values()))
    except:
        return default

def remove_prefixes(text, prefixes):
    if not isinstance(prefixes, (list, tuple)):
        prefixes = [prefixes]

    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):]

    return text


def remove_suffixes(text, suffixes):
    if not isinstance(suffixes, (list, tuple)):
        suffixes = [suffixes]

    for suffix in suffixes:
        if text.endswith(suffix):
            text = text[0:-len(suffix):]

    return text


def update_dict_without_overwrite(original, new):
    original.update({key: new[key] for key in new if key not in original})


def camel_case_split(word):
    return '_'.join(re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', word)).lower()


def debug_print(*objects, sep=' ', end='\n', flush=True):
    print('[DEBUG]', *objects, sep=sep, end=end, flush=flush)

def log(text, items, logging_level=None, matching='all', pause_on_debug=False):

    # matching specifies which logging levels should display the text

    if logging_level is None:
        logging_level = text
    if matching != 'all':
        if not isinstance(matching, (tuple, list)):
            matching = [matching]

        if logging_level == 'none' or logging_level not in matching:
            # do nothing
            return

    if not isinstance(items, (tuple, list)):
        items = [items]

    for item in items:
        print('[{}]'.format(text), item, flush=True)

    # TODO fix ?
    if pause_on_debug:# and mode == 'errors'
        input()

def replace_with_underscores(text, sep='-'):
    return text.replace(sep, '_')

def multi_get(dictionary, *keys, default = None):
    current = dictionary
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return default
    return current

def safe_convert_text(text):
    message = emoji.demojize(text)

    try:
        return message.encode(
            'utf-8', 'ignore').decode('utf-8', 'ignore')
    except UnicodeEncodeError:
        # in the rare case that standard output does not support utf-8
        return message.encode(
            'ascii', 'ignore').decode('ascii', 'ignore')


def safe_print_text(text):
    """
    Ensure printing to standard output can be done safely (especially on Windows).
    There are usually issues with printing emojis and non utf-8 characters.

    """
    print(safe_convert_text(text), flush=True)
