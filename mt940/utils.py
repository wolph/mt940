from __future__ import annotations

import enum
import typing

T = typing.TypeVar('T')


def coalesce(*args: T | None) -> T | None:
    """
    Return the first non-None argument.

    Examples:
        >>> coalesce()
        >>> coalesce(0, 1)
        0
        >>> coalesce(None, 0)
        0

    Returns:
        The first non-None argument or None if all are None.
    """
    return next((arg for arg in args if arg is not None), None)


class Strip(enum.IntFlag):
    """
    Enumeration of options for stripping whitespace in strings.

    Attributes:
        NONE: Do not strip any whitespace.
        LEFT: Strip leading whitespace.
        RIGHT: Strip trailing whitespace.
        BOTH: Strip both leading and trailing whitespace.
    """

    NONE = 0
    LEFT = 1
    RIGHT = 2
    BOTH = LEFT | RIGHT


def join_lines(string: str, strip: Strip = Strip.BOTH) -> str:
    """
    Join strings together and strip whitespace in between if needed.

    Args:
        string: The string with lines to join.
        strip: Strip options from the Strip enum.

    >>> join_lines('  line1\\nline2  \\n line3 ')
    'line1line2line3'
    >>> join_lines('  line1\\nline2  \\n line3 ', strip=Strip.LEFT)
    'line1line2  line3 '
    >>> join_lines('  line1\\nline2  \\n line3 ', strip=Strip.RIGHT)
    '  line1line2 line3'
    >>> join_lines('  line1\\nline2  \\n line3 ', strip=Strip.NONE)
    '  line1line2  line3 '


    Returns:
        The joined string.
    """
    strip_left = bool(strip & Strip.LEFT)
    strip_right = bool(strip & Strip.RIGHT)

    strip_func: typing.Callable[[str], str]
    if strip_left and strip_right:
        strip_func = lambda s: s.strip()  # noqa: E731
    elif strip_left:
        strip_func = lambda s: s.lstrip()  # noqa: E731
    elif strip_right:
        strip_func = lambda s: s.rstrip()  # noqa: E731
    else:
        strip_func = lambda s: s  # noqa: E731

    lines = [strip_func(line) for line in string.splitlines()]
    return ''.join(lines)
