"""Read MT940 sources and turn them into transaction collections.

Format
---------------------

Sources:

.. _Swift for corporates: http://www.sepaforcorporates.com/\
    swift-for-corporates/account-statement-mt940-file-format-overview/
.. _Rabobank MT940: https://www.rabobank.nl/images/\
    formaatbeschrijving_swift_bt940s_1_0_nl_rib_29539296.pdf

 - `Swift for corporates`_
 - `Rabobank MT940`_

::

    [] = optional
    ! = fixed length
    a = Text
    x = Alphanumeric, seems more like text actually. Can include special
        characters (slashes) and whitespace as well as letters and numbers
    d = Numeric separated by decimal (usually comma)
    c = Code list value
    n = Numeric
"""

from __future__ import annotations

import os
import pathlib
import re
from typing import TYPE_CHECKING

import mt940

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ._types import Processors, Source
    from .models import Transactions
    from .options import Options


def _decode(data: bytes, encoding: str | None) -> str:
    """Decode raw statement bytes, trying ``encoding`` first.

    ``utf-8`` and ``cp852`` are the fallbacks. ``cp852`` maps every byte
    value, so it never fails and always closes the chain.

    Args:
        data: The raw bytes as read from the file or handle.
        encoding: The caller's preferred encoding, or ``None``.

    Returns:
        The decoded text.
    """
    for enc in (encoding, 'utf-8'):
        if not enc:
            continue
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode('cp852')


def _read(src: Source, encoding: str | None = None) -> str:
    """Read raw mt940 data from a file handle, path or string and decode it.

    Args:
        src: A path, raw ``str``/``bytes`` data or an open file handle. A
            ``str`` or ``bytes`` value that does not name an existing file
            is taken to be the statement data itself.
        encoding: The encoding to try first for ``bytes`` data.

    Returns:
        The decoded statement text without a leading byte-order mark.

    Raises:
        FileNotFoundError: When ``src`` is a path-like object that does not
            name an existing file.
    """
    data: str | bytes
    if not isinstance(src, (str, bytes, os.PathLike)):
        data = src.read()
    elif os.path.isfile(src):  # noqa: PTH113 (bytes paths are accepted too)
        data = pathlib.Path(os.fsdecode(src)).read_bytes()
    elif isinstance(src, os.PathLike):
        raise FileNotFoundError(os.fsdecode(src))
    else:
        data = src

    if isinstance(data, bytes):
        data = _decode(data, encoding)

    # Strip a leading byte-order mark (U+FEFF). A BOM survives decoding as
    # U+FEFF for UTF-8 input (and for UTF-16 only when an explicit
    # utf-16-le/-be encoding is passed). It is not whitespace, so it would
    # otherwise displace the first `:20:` off the start-of-line tag anchor and
    # silently drop that tag's data.
    return data.removeprefix('\ufeff')


def parse(
    src: Source,
    encoding: str | None = None,
    processors: Processors | None = None,
    tags: dict[int | str, mt940.tags.Tag] | None = None,
    transaction_boundary: Iterable[str] | None = None,
    *,
    options: Options | None = None,
) -> Transactions:
    """Parse MT940 data into a single :class:`~mt940.models.Transactions`.

    Args:
        src: A file handle, a filename to read, or the raw data as
            ``str``/``bytes``.
        encoding: Optional encoding override for byte input.
        processors: Optional extra pre/post processors.
        tags: Optional extra or overriding tag parsers.
        transaction_boundary: Optional iterable of tag *slugs* that each start
            a new transaction (issue #110). By default only ``:61:`` starts a
            transaction; pass e.g. ``{'transaction_reference_number'}`` to also
            start one on every ``:20:``. Omit it to keep the legacy behaviour.
        options: Opt-in behaviours, see :class:`mt940.options.Options`. Omit
            to parse exactly like release 5.0.0.

    Returns:
        The parsed collection of transactions.
    """
    data = _read(src, encoding)
    transactions = mt940.models.Transactions(
        processors,
        tags,
        transaction_boundary=transaction_boundary,
        options=options,
    )
    _ = transactions.parse(data)

    return transactions


def parse_statements(
    src: Source,
    encoding: str | None = None,
    processors: Processors | None = None,
    tags: dict[int | str, mt940.tags.Tag] | None = None,
    transaction_boundary: Iterable[str] | None = None,
    *,
    options: Options | None = None,
) -> list[Transactions]:
    """Parse an mt940 file that contains multiple statement blocks.

    Unlike :func:`parse`, which merges everything into a single
    :class:`~mt940.models.Transactions`, this splits the input on ``:20:``
    statement boundaries and parses each block into its own
    :class:`~mt940.models.Transactions`. Use it for files that concatenate
    several statements (e.g. balance-only blocks), where a single
    ``Transactions`` would only keep the last block's statement-level data such
    as the opening/closing/available balances (issue #107).

    Each ``:20:`` is treated as the start of a new statement, matching the
    standard where ``:20:`` is the once-per-statement transaction reference.
    This is therefore mutually exclusive with
    ``transaction_boundary={'transaction_reference_number'}`` (issue #110),
    which instead treats ``:20:`` as an *intra*-statement transaction boundary;
    the two target different, non-standard bank formats -- don't combine them.

    Args:
        src: A file handle, a filename to read, or the raw data as
            ``str``/``bytes``.
        encoding: Optional encoding override for byte input.
        processors: Optional extra pre/post processors (applied per block).
        tags: Optional extra or overriding tag parsers (applied per block).
        transaction_boundary: See :func:`parse` (and the note above).
        options: See :func:`parse`.

    Returns:
        One :class:`~mt940.models.Transactions` per statement block.
    """
    data = _read(src, encoding)
    statements: list[Transactions] = []
    for block in re.split(r'(?m)^(?=:20:)', data):
        if not block.strip().startswith(':20:'):
            # Drop any leading header / empty chunk before the first :20:.
            continue
        transactions = mt940.models.Transactions(
            processors,
            tags,
            transaction_boundary=transaction_boundary,
            options=options,
        )
        _ = transactions.parse(block)
        statements.append(transactions)

    return statements
