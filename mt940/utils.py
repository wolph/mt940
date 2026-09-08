"""Small, dependency-free helpers shared across the package.

Contains :func:`coalesce` (first non-``None`` value) and :func:`join_lines`
(whitespace-aware line joining) together with the :class:`Strip` flag enum that
configures the latter.
"""

from __future__ import annotations

import enum
import typing

#: Value type preserved by :func:`coalesce` when choosing a non-None input.
T = typing.TypeVar('T')


def coalesce(*args: T | None) -> T | None:
    """Return the first argument that is not ``None``.

    Args:
        *args: Values to inspect in their supplied order. False values such as
            zero, an empty string and ``False`` are eligible results.

    Returns:
        The first non-``None`` value, or ``None`` for no arguments or all
        ``None`` arguments. The selected value is returned without copying.

    Examples:
        >>> coalesce()
        >>> coalesce(None, 0, 1)
        0
        >>> coalesce('', 'fallback')
        ''
    """
    return next((arg for arg in args if arg is not None), None)


class Strip(enum.IntFlag):
    """Bit flags controlling whitespace removal from each joined line.

    Combine :attr:`LEFT` and :attr:`RIGHT` with ``|``, or use :attr:`BOTH`.
    :func:`join_lines` always removes line boundaries, including with
    :attr:`NONE`. These flags only control whitespace within each line.
    """

    NONE = 0
    """Do not strip any whitespace."""

    LEFT = 1
    """Strip leading whitespace."""

    RIGHT = 2
    """Strip trailing whitespace."""

    BOTH = LEFT | RIGHT
    """Strip both leading and trailing whitespace."""


def join_lines(string: str, strip: Strip = Strip.BOTH) -> str:
    r"""Remove line boundaries and optionally strip each line's whitespace.

    Args:
        string: Text split with :meth:`str.splitlines`. Its recognised Unicode
            line separators are removed along with ordinary newlines.
        strip: :class:`Strip` flags applied to each line before concatenation.
            The default strips both ends of every line.

    Returns:
        Lines concatenated without an inserted separator. Empty input returns
        an empty string. Spaces inside a line remain unchanged.

    Examples:
        >>> join_lines('  line1\nline2  \n line3 ')
        'line1line2line3'
        >>> join_lines('  line1\nline2  \n line3 ', strip=Strip.LEFT)
        'line1line2  line3 '
        >>> join_lines('  line1\nline2  \n line3 ', strip=Strip.RIGHT)
        '  line1line2 line3'
        >>> join_lines('  line1\nline2  \n line3 ', strip=Strip.NONE)
        '  line1line2  line3 '
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
