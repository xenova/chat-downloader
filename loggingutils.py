import logging
import string
import time
from datetime import datetime
import collections.abc
import sys
import os
import contextlib
import traceback
import inspect
import atexit

class loggerProperty:
    """
    This descriptor serves multiple purposes:
    1. Workaround for class variable initialization unable to access current class name.
    2. Delay actual logging until logging is "initialized" (determined by len(logging.root.handlers) != 0)
    The created logger doesn't define its own level or handlers by default, but that can be configured via logger_init.

    `loggingutils.basicConfig` keyword arguments (including `lenient` and `propagate`) can also be passed to loggerProperty.
    If any such arguments are passed (`**basic_config_kwargs`), `loggingutils.basicConfig(logger, **basic_config_kwargs)`
    will be called upon first access of the logger property.

    `logger_init(logger, instance, owner)` is called upon first access of the logger property,
    after the above optional `loggingutils.basicConfig` call.

    `loggerProperty` can be used as a decorator, e.g.
        @loggerProperty(...)
        def logger(self, instance, owner): # where self is the new logger
            return ...
    is effectively equivalent to:
        logger = loggerProperty(logger_init=lambda self, instance, owner: ..., ...)
    """

    __slots__ = 'logger', 'actual_logger', 'logger_name', 'logger_init', 'basic_config_kwargs'

    def __init__(self, logger_name=None, logger_init=None, **basic_config_kwargs):
        self.logger = None
        self.actual_logger = None
        self.logger_name = logger_name
        self.logger_init = logger_init
        self.basic_config_kwargs = basic_config_kwargs

    def __call__(self, logger_init):
        self.logger_init = logger_init
        return self

    def __get__(self, instance=None, owner=None):
        if self.logger is None:
            if not self.logger_name:
                self.logger_name = instance.__class__.__qualname__ if instance else owner.__qualname__ if owner else None
            orig_logger = logging.getLogger(self.logger_name)
            if self.basic_config_kwargs:
                basicConfig(orig_logger, **self.basic_config_kwargs)
            if self.logger_init:
                self.logger_init = self.resolve_func(self.logger_init, instance, owner)
                self.logger = self.logger_init(orig_logger, instance, owner)
            else:
                self.logger = orig_logger
            self.actual_logger = getLogger(self.logger) # ensure we get the Logger and not a LoggerAdapter
            if self.logging_uninitialized():
                self.logger = _PreinitLogger(self.logger, self)
        elif isinstance(self.logger, _PreinitLogger):
            self.logger._try_preinit_flush()
        return self.logger

    def logging_uninitialized(self):
        return len(logging.root.handlers) == 0 # assume this means that logging isn't initialized yet

    # allow given func to be a descriptor like a staticmethod-wrapped function
    @staticmethod
    def resolve_func(func, instance, owner):
        while (get := getattr(func, '__get__', None)) is not None:
            next_func = get(instance, owner) # pylint: disable=not-callable # __get__ should be callable
            if next_func is None or func is next_func: # if func is a method, func.__get__(...) is func
                break
            func = next_func
        return func

# if loggingProperty.logging_uninitialized(), this is used to hold log records until logging is initialized
class _PreinitLogger(logging.LoggerAdapter):
    __slots__ = '_logger_property', '_orig_level', '_preinit_records'

    _TEMP_LOG_LEVEL = -9999

    def __init__(self, logger, logger_property):
        super().__init__(logger, None)
        actual_logger = logger_property.actual_logger
        self._logger_property = logger_property
        self._orig_level = actual_logger.level
        self._preinit_records = []
        actual_logger.addFilter(self._preinit_filter) # filter is convenient for capturing created records
        actual_logger.level = self._TEMP_LOG_LEVEL # since log level check happens before filter, ensure that check always succeeds
        atexit.register(self._preinit_flush)

    def log(self, level, msg, *args, **kwargs):
        # note: client code may still be using this instance even after logging is initialized
        # (e.g. if it doesn't get the logger property again after logging is initialized),
        # so this still needs to be functional after logging is initialized
        self._try_preinit_flush()
        return self.logger.log(level, msg, *args, **kwargs)

    def _preinit_filter(self, record):
        if self._try_preinit_flush():
            return True
        self._preinit_records.append(record)
        return False

    def _try_preinit_flush(self):
        if self._logger_property and not self._logger_property.logging_uninitialized():
            self._preinit_flush()
            return True
        return False

    def _preinit_flush(self):
        actual_logger = self._logger_property.actual_logger
        actual_logger.removeFilter(self._preinit_filter)
        actual_logger.setLevel(self._orig_level)
        self._logger_property.logger = self.logger
        for record in self._preinit_records:
            if actual_logger.isEnabledFor(record.levelno): # recheck log level
                actual_logger.handle(record)
        self._preinit_records.clear()
        atexit.unregister(self._preinit_flush)
        self._logger_property = None


# copy of logging._StderrHandler, replacing stderr with stdout
class StdoutHandler(logging.StreamHandler):
    """
    This class is like a StreamHandler using sys.stdout, but always uses
    whatever sys.stderr is currently set to rather than the value of
    sys.stdout at handler construction time.
    """
    def __init__(self, level=logging.NOTSET):
        """
        Initialize the handler.
        """
        logging.Handler.__init__(self, level)

    @property
    def stream(self):
        return sys.stdout


# for parity with above StdoutHandler
StderrHandler = logging._StderrHandler


class lenientFormatStyle(contextlib.ContextDecorator):
    """
    Provides a context where when initializing `Formatter`s, the format string can contain substitution keywords
    (e.g. `%(key)s` for '%' style, `{key}` for '{' style, `${key}` for '$' style) that don't match any attributes in
    `LogRecord` or keys in the `extra` dict (whether passed via logger calls or via `LoggerAdapter`.

    Normally, this would cause the logging of the record to fail (logged to `stderr` by default - see `Handler.handleError`).
    In the "lenient" context this class provides, such failed substitutions instead result in empty strings being substituted.

    This class can be used in one of two ways:
    * as a context manager:
        with lenientFormatStyle():
            ... Formatter(...) # only Formatter construction needs to be done in the with block
    * as a decorator:
        @lenientFormatStyle()
        def foo(...):
            ... Formatter(...) # only Formatter construction needs to be done in the function
    """

    class PercentStyle(logging.PercentStyle):
        def _format(self, record):
            return self._fmt % _LenientMapWrapper(record.__dict__)

    class StrFormatStyle(logging.StrFormatStyle):
        def _format(self, record):
            return _LenientFormatter().vformat(self._fmt, (), record.__dict__)

    class StringTemplateStyle(logging.StringTemplateStyle):
        def _format(self, record):
            return self._tpl.substitute(_LenientMapWrapper(record.__dict__))

    __slots__ = 'orig_STYLES'

    _STYLES = {
        '%': (PercentStyle, logging._STYLES['%'][1]),
        '{': (StrFormatStyle, logging._STYLES['{'][1]),
        '$': (StringTemplateStyle, logging._STYLES['$'][1]),
    }

    def __enter__(self):
        logging._acquireLock()
        self.orig_STYLES = logging._STYLES
        logging._STYLES = self._STYLES

    def __exit__(self, *exc):
        logging._STYLES = self.orig_STYLES
        logging._releaseLock()

class _LenientFormatter(string.Formatter):
    __slots__ = ()
    def get_value(self, key, args, kwargs):
        try:
            return super().get_value(key, args, kwargs)
        except LookupError:
            return ''

class _LenientMapWrapper(collections.abc.Mapping):
    __slots__ = 'map'
    def __init__(self, map):
        self.map = map
    def __getitem__(self, key):
        return self.map.get(key, '')
    def __iter__(self):
        return iter(self.map)
    def __len__(self):
        return len(self.map)
    def __str__(self):
        return str(self.map)
    def __repr__(self):
        return repr(self.map)


class FormatLoggerAdapter(logging.LoggerAdapter):
    """
    `LoggerAdapter` that allows usage of any format style: `printf` ('%'), `str.format`/`string.Formatter` ('{'), `string.Template` ('$')
    in `logger.log(level, msg_format, ...)` and `logger.<level>(msg_format, ...)` calls.

    This does not affect how the format string in `Formatter` is handled, so it's possible to have a `FormatLoggerAdapter` over a logger
    with a handler's formatter having different format `style`s.
    """

    __slots__ = 'style'

    log_kwarg_names = [param.name for param in inspect.signature(logging.Logger._log).parameters.values()
                       if param.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD and param.default is not inspect.Parameter.empty]

    def __init__(self, logger, style, extra=None):
        if style not in logging._STYLES:
            raise ValueError('Style must be one of: ' + ','.join(logging._STYLES.keys()))
        super().__init__(logger, extra)
        self.style = style

    def log(self, level, msg, *args, **kwargs):
        if self.isEnabledFor(level):
            if self.style == '{':
                msg, kwargs = self.process(msg, kwargs)
                if not isinstance(msg, str):
                    msg = str(msg)
                msg = string.Formatter().vformat(msg, args, kwargs)
                if kwargs:
                    self._sanitize_kwargs(kwargs)
                args = ()
            elif self.style == '$':
                if isinstance(msg, string.Template):
                    msg = msg.template
                msg, kwargs = self.process(msg, kwargs)
                if not isinstance(msg, str):
                    msg = str(msg)
                if args or kwargs:
                    if len(args) == 1 and isinstance(args[0], collections.abc.Mapping):
                        map = args[0]
                        if kwargs:
                            if not isinstance(map, collections.abc.MutableMapping):
                                map = dict(map)
                            map.update(kwargs)
                    else:
                        map = kwargs
                    msg = string.Template(msg).substitute(map)
                    if kwargs:
                        self._sanitize_kwargs(kwargs)
                else:
                    msg = string.Template(msg).substitute()
                args = ()
            else: # if self.style == '%'
                msg, kwargs = self.process(msg, kwargs)
            self.logger._log(level, msg, args, **kwargs)

    def _sanitize_kwargs(self, kwargs):
        del_keys = []
        for k in kwargs:
            if k not in self.log_kwarg_names:
                del_keys.append(k)
        for k in del_keys:
            del kwargs[k]


def contextdecorator(dec_func):
    """
    An alternate to `contextlib.contextmanager` intended to be used only as a decorator.

    To illustrate the difference, `@contextmanager` in decorator form is used to pass "fixed" arguments to the decorator:
        @contextmanager
        def decorator(x):
            <start>
            try:
                yield ...
            finally:
                <end>
        @decorator(<x>) # note how decorator is "called" here - decorator's x is "fixed" to always be <x> when foo is called
        def foo(a, b):
            ...
    while `@contextdecorator` is used to pass arguments from a call to the decoree on to the decorator:
        @contextdecorator
        def decorator(a, b):
            <start>
            try:
                yield ...
            finally:
                <end>
        @decorator      # note how decorator is NOT "called" here - foo's arguments are passed on to the decorator each call
        def foo(a, b):
            ...

    This doesn't really belong in this module, but it's convenient for defining local loggers, e.g.
        @contextdecorator
        def with_context(self, id, *args, **kwargs):
            self.logger = LoggerAdapter(self.__class__.logger, {'context': id})
            try:
                yield self.logger
            finally:
                del self.logger
        @with_context
        def foo(self, id, ...):
            ...
    """
    @contextlib.wraps(dec_func)
    def helper(func):
        @contextlib.wraps(func)
        def inner(*args, **kwargs):
            with contextlib._GeneratorContextManager(dec_func, args, kwargs):
                func(*args, **kwargs)
        return inner
    return helper


class DateFileHandler(logging.FileHandler):
    """
    This provides similar functionality to `logging.handlers.TimedRotatingFileHandler`, the main difference being:

    * `DateFileHandler`: always writes to new date suffixed filenames at intervals
    * `TimedRotatingFileHandler`: always writes to a base filename, then rotates it to the date-suffixed filenames at intervals

    The latter is problematic because the rotation can fail if something else has that base filename opened (e.g. auto backups),
    which IMO is a bad tradeoff for the advantage of allowing `tail -f` on a single log file.
    
    `TimedRotatingFileHandler` also does not make it easy to append another suffix (like a file extension) to the date-suffixed filenames.
    """

    __slots__ = '_filename_format', '_date_interval', '_rotate_timestamp'

    def __init__(self, filename_format, date_interval=None, *args, **kwargs):
        self._filename_format = filename_format
        self._date_interval = date_interval
        self._rotate_timestamp, filename = self._rotate_timestamp_and_filename(datetime.now())
        super().__init__(filename, *args, **kwargs)

    def emit(self, record):
        if self._rotate_timestamp and time.time() > self._rotate_timestamp:
            self._rotate_timestamp, self.baseFilename = self._rotate_timestamp_and_filename(datetime.fromtimestamp(record.created))
            old_stream = self.setStream(super()._open())
            try:
                old_stream.close()
            except:
                traceback.print_exc(file=sys.stderr)
        super().emit(record)

    def _rotate_timestamp_and_filename(self, date):
        rotate_timestamp = None
        if self._date_interval:
            filename = date.strftime(self._filename_format)
            if filename != self._filename_format: # if filename_format has any format codes
                # round current local date according to date format
                rotate_timestamp = (datetime.strptime(filename, self._filename_format).astimezone() + self._date_interval).timestamp()
        return (rotate_timestamp, os.path.abspath(filename))


def getLogger(name_or_logger=None):
    """
    If argument is a `logging.Logger`, returns as-is.

    If argument has a `logger` attribute (such as `logging.LoggerAdapter`), recursively returns `getLogger(argument.logger)`,
    even if there are multiple nested `LoggerAdapter`s.

    Otherwise, returns `logging.getLogger(argument)`.
    """
    if isinstance(name_or_logger, logging.Logger):
        return name_or_logger
    # not using logger = getattr(name_or_logger, 'logger', None) since None is a valid getLogger argument (root logger)
    if hasattr(name_or_logger, 'logger'):
        logger = name_or_logger.logger
        if logger != name_or_logger: # avoid infinite loop if name_or_logger.logger refers to itself
            return getLogger(logger)
    return logging.getLogger(name_or_logger)

def basicConfig(logger, **kwargs):
    """
    `logging.basicConfig` primarily for non-root loggers (although still useful for root logger for lenient style - see below).

    :param propagate: if given, sets logger.propagate to its value.

    If `propagate` keyword arg is given, sets logger.propagate to its value.
    
    If `lenient` keyword arg is truthy, effectively decorates this function with `@lenientFormatStyle()`.

    Returns the given logger (now configured) for convenience.
    """
    if kwargs.pop('lenient', None):
        lenient = lenientFormatStyle()
        ctx_enter = lenient.__enter__
        ctx_exit = lenient.__exit__
    else:
        ctx_enter = logging._acquireLock
        ctx_exit = logging._releaseLock
    propagate = kwargs.pop('propagate', None)
    ctx_enter()
    orig_root = logging.root
    try:
        logging.root = logger
        logging.basicConfig(**kwargs)
        if propagate is not None:
            logger.propagate = propagate
    finally:
        logging.root = orig_root
        ctx_exit()
    return logger


def addLevelName(level, level_name):
    """
    Usage (to workaround `pylint` inability to recognize new setattr'd attributes):
        logging.<NAME>, logging.<name>, logging.Logger.<name>, logging.LoggerAdapter.<name> = logging.addLevelName(<level>, <NAME>)

    More complete version of `logging.addLevelName(<level>, <NAME>)` that also adds (if not yet defined):
        logging.<NAME> = <level>
        logging.<name>(msg, *args, **kwargs)
        logging.Logger.<name>(self, msg, *args, **kwargs)
        logging.LoggerAdapter.<name>(self, msg, *args, **kwargs)
    """
    if not level_name.isupper():
        raise ValueError(f"Expected all uppercase level name: {level_name}")
    if not hasattr(logging, level_name) or level_name not in logging._nameToLevel:
        setattr(logging, level_name, level)
        logging.addLevelName(level, level_name)
    func_name = level_name.lower()
    # need to define separate functions (lambdas here) for each of these, since need separate function instances
    _def_method(logging, func_name, lambda msg, *args, **kwargs: logging.log(level, msg, *args, **kwargs))
    _def_method(logging.Logger, func_name, lambda self, msg, *args, **kwargs: self.log(level, msg, *args, **kwargs))
    _def_method(logging.LoggerAdapter, func_name, lambda self, msg, *args, **kwargs: self.log(level, msg, *args, **kwargs))
    return getattr(logging, level_name), getattr(logging, func_name), getattr(logging.Logger, func_name), getattr(logging.LoggerAdapter, func_name)

def _def_method(cls, name, func):
    if not hasattr(cls, name):
        func.__name__ = name
        if inspect.ismodule(cls):
            func.__qualname__ = name
            func.__module__ = cls.__name__
        else:
            func.__qualname__ = f"{cls.__qualname__}.{name}"
            func.__module__ = cls.__module__
        setattr(cls, name, func)


# for debugging
def _print_err(*args):
    print(inspect.currentframe().f_back.f_code.co_name + ':', *args, file=sys.__stderr__, flush=True)
