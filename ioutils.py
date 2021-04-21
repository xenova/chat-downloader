from datetime import datetime

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
    Intended for allowing multiple outputs for a single file object.
    
    Based off https://stackoverflow.com/a/16551730
    """

    __slots__ = 'files', 'attrwraps'

    def __init__(self, *files):
        self.files = files
        self.attrwraps = {}

    # explicit def for efficiency
    def write(self, s):
        for f in self.files:
            f.write(s)

    # explicit def for efficiency
    def flush(self):
        for f in self.files:
            f.flush()

    # for any other method, delegate to slower __getattr__
    def __getattr__(self, attr, *args):
        attr = self.attrwraps.get(attr)
        if attr is not None:
            return attr
        def wrap(*args2, **kwargs2):
            for f in self.files:
                result = getattr(f, attr, *args)(*args2, **kwargs2)
            return result
        self.attrwraps[attr] = wrap
        return wrap
