import threading
import _thread
import time
import sys


POLLING_TIME = 0.1

SP = ' '
CR = '\r'
LF = '\n'
CRLF = CR + LF


class TimeoutOccurred(Exception):
    """Thrown when a timeout has occurred"""
    pass


def echo(text):
    sys.stdout.write(text)
    sys.stdout.flush()


# Adapted from https://github.com/johejo/inputimeout

try:
    import msvcrt

    def win_timed_input(timeout, prompt, newline):
        echo(prompt)
        begin = time.monotonic()
        end = begin + timeout
        line = ''

        while time.monotonic() < end:
            if msvcrt.kbhit():
                c = msvcrt.getwche()
                if c in (CR, LF):
                    echo(CRLF)
                    return line
                if c == '\003':
                    raise KeyboardInterrupt
                if c == '\b':
                    line = line[:-1]
                    cover = SP * len(prompt + line + SP)
                    echo(CR + cover + CR + prompt + line)
                else:
                    line += c

            time.sleep(POLLING_TIME)

        if newline:
            echo(CRLF)

        raise TimeoutOccurred

    _timed_input = win_timed_input

except ImportError:
    import selectors
    import termios

    def posix_timed_input(timeout, prompt, newline):
        echo(prompt)
        sel = selectors.DefaultSelector()
        sel.register(sys.stdin, selectors.EVENT_READ)
        events = sel.select(timeout)

        if events:
            key, _ = events[0]
            return key.fileobj.readline().rstrip(LF)
        else:
            if newline:
                echo(LF)
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
            raise TimeoutOccurred

    _timed_input = posix_timed_input


def timed_input(timeout=None, prompt='', newline=False, default=None):
    if timeout is None:
        return input(prompt)
    try:
        return _timed_input(timeout, prompt, newline)
    except TimeoutOccurred:
        return default


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


def interruptible_sleep(secs, poll_time=POLLING_TIME):
    start_time = time.time()

    while time.time() - start_time <= secs:
        time.sleep(poll_time)
