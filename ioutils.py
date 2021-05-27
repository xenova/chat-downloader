from datetime import datetime
import io

class TimestampPrefixFileWrapper:
    """
    Intended to wrap file-like objects like sys.stdout/stderr in cases where logging module shouldn't be used
    (e.g. logging module outputs its own errors to stderr, so this can be used to wrap stderr).
    """

    __slots__ = 'f', 'datefmt', 'next_line_needs_prefix'

    def __init__(self, f, datefmt):
        self.f = f
        self.datefmt = datefmt
        self.next_line_needs_prefix = True

    def write(self, s):
        if s == '':
            self.f.write('')
            return
        lines = s.splitlines(keepends=True) # since s != '', len(lines) >= 1
        if self.next_line_needs_prefix or len(lines) != 1:
            if self.next_line_needs_prefix:
                lines.insert(0, '')
            s = f"[{datetime.now():{self.datefmt}}] ".join(lines)
        self.f.write(s)
        last_line = lines[-1] # since keepends=True, guaranteed to be non-empty
        self.next_line_needs_prefix = len(last_line.splitlines()[0]) != len(last_line) # handles universal newlines

    def flush(self): # explicit def for efficiency
        self.f.flush()

    def __getattr__(self, name):
        return self.f.__getattr__(self, name)


class MultiFile:
    """
    Allows multiple file-like outputs via single file-like object.
    Other operations also are performed on each file, but only the result on the last file is returned.
    
    Based off https://stackoverflow.com/a/16551730
    """

    __slots__ = '_files', '_wraps'

    def __init__(self, *files):
        self._files = files
        self._wraps = {}

    # explicit def for efficiency
    def write(self, s):
        for f in self._files:
            f.write(s)

    # explicit def for efficiency
    def flush(self):
        for f in self._files:
            f.flush()

    # for any other method, delegate to slower __getattr__
    # assumes all other accessed attributes are methods
    def __getattr__(self, name):
        try:
            wrap = self._wraps[name]
        except KeyError:
            def wrap(*args, **kwargs):
                for f in self._files:
                    result = getattr(f, name)(*args, **kwargs)
                return result
            self._wraps[name] = wrap
        return wrap

io.IOBase.register(MultiFile)
