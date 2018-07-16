"""
Console logging system.
"""

import datetime
import os
import sys
import re


# ASCII escape colours
_ESCAPE_BLACK = '\u001b[30m'
_ESCAPE_DARK_GREY = '\u001b[30;1m'
_ESCAPE_DARK_RED = '\u001b[31m'
_ESCAPE_RED = '\u001b[31;1m'
_ESCAPE_DARK_GREEN = '\u001b[32m'
_ESCAPE_GREEN = '\u001b[32;1m'
_ESCAPE_DARK_YELLOW = '\u001b[33m'
_ESCAPE_YELLOW = '\u001b[33;1m'
_ESCAPE_DARK_BLUE = '\u001b[34m'
_ESCAPE_BLUE = '\u001b[34;1m'
_ESCAPE_DARK_MAGENTA = '\u001b[35m'
_ESCAPE_MAGENTA = '\u001b[35;1m'
_ESCAPE_DARK_CYAN = '\u001b[36m'
_ESCAPE_CYAN = '\u001b[36;1m'
_ESCAPE_GREY = '\u001b[37m'
_ESCAPE_WHITE = '\u001b[37;1m'
_ESCAPE_BOLD = '\u001b[1m'
_ESCAPE_UNDERLINE = '\u001b[4m'
_ESCAPE_REVERSED = '\u001b[7m'
_ESCAPE_RESET = '\u001b[0m'


def _ttysize():
    """Returns the size of the terminal (width, height)"""
    rows, columns = os.popen('stty size', 'r').read().split()
    return (int(columns), int(rows))


def _escape(text, esc_code):
    """Escape the given text with the given escape code"""

    escaped = text  # by default, we leave the text unchanged

    # escape the text if a valid escape code is given
    if esc_code:
        escaped = "%s%s%s" % (esc_code, text, _ESCAPE_RESET)

    return escaped


def _cursor_hide():
    """Hide the cursor from the terminal"""
    sys.stdout.write("\033[?25l")


def _cursor_show():
    """Show the cursor from the terminal"""
    sys.stdout.write("\033[?25h")


def _log_format(colour, message):
    """
    Format a log mesage for output
    :param colour: Colour code for the message text
    :param message: The message to output
    """

    formatted = ""

    utctime = datetime.datetime.utcnow()
    timeformatted = utctime.strftime('%Y-%m-%d %H:%M:%S')

    formatted += _escape(timeformatted, _ESCAPE_DARK_GREY)
    formatted += "  "
    formatted += _escape(message, colour)

    return formatted


def _strip_escape_codes(unclean):
    """Strips out the ANSI escape codes from the given string"""

    # strip out the escape codes
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    stripped = ansi_escape.sub('', unclean)

    return stripped


def _log_header_len():
    """Returns the size of the header included by _log_format()"""

    # get an empty log message to measure its length
    logger_header = _log_format('', '')

    # strip out the ANSI escape code
    logger_header_stripped = _strip_escape_codes(logger_header)

    return len(logger_header_stripped)


def _log(colour, message):
    """Log given mesage to the console"""

    (width, height) = _ttysize()

    # EOL is first so last log message is always at bottom of terminal window


    # hide the cursor otherwise it gltiches when updating frequently
    _cursor_hide()

    # output the formatted log message
    logstr = _log_format(colour, message)
    sys.stdout.write(logstr)

    # calculate length of the log message, visible chars only
    logstr_stripped = _strip_escape_codes(logstr)
    logstr_len = len(logstr_stripped)

    # clear the remainder of the line by filling it with spaces, i.e. ' '
    if logstr_len % width:
        clearline = ''
        for x in range(logstr_len % width, width):
            clearline += " "
        sys.stdout.write(clearline)

    sys.stdout.write("\n")

    sys.stdout.flush()


def error(message):
    """
    Log an error message to stderr.
    :param message: The message to log to the error output
    """
    _log(_ESCAPE_DARK_RED, message)


def log(message):
    """
    Log a message to the console
    :param message: The message to output to the console.
    """
    _log(_ESCAPE_DARK_GREEN, message)


def system(message):
    """
    Log a system message to the console, shouldn't actually be used by the bot
    :param message: The message to output to the console.
    """
    # _log(_ESCAPE_GREEN+_ESCAPE_BOLD, message)  # This would be nice but doesn't work on windows
    _log(_ESCAPE_DARK_YELLOW, message)


def hr():
    """Outputs a horizontal rule / line."""

    (width, ) = _ttysize()

    # build the horizontal line
    row = ""
    for i in range(0, width-_log_header_len()):
        row += "#"

    # output the line
    log(row)


def back(num_lines):
    """
    Back the cursor up given number of lines. Allows for overwriting sections
    of text on the console. Good for updating a status message
    """

    sys.stdout.write("\u001b[1000D") # move all the way to left of screen (1000 chars should do it)
    sys.stdout.write("\u001b[%dA" % num_lines) # move back 1 line
    sys.stdout.flush()


def shutdown():
    """
    Shutdown the console system and reset anything changed before returning
    the user to the prompt.
    """

    _cursor_show()
