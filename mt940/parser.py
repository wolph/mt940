"""
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
import re
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

import mt940

if TYPE_CHECKING:
    from ._types import Processors, Source
    from .models import Transactions


def _read(src: Any, encoding: str | None = None) -> str:
    """Read raw mt940 data from a file handle, path or string and decode it."""

    def safe_is_file(filename: Any) -> bool:
        try:
            return os.path.isfile(filename)
        except ValueError:  # pragma: no cover
            return False

    if hasattr(src, 'read'):  # pragma: no branch
        data = src.read()
    elif safe_is_file(src):
        with open(src, 'rb') as fh:
            data = fh.read()
    else:  # pragma: no cover
        data = src

    if hasattr(data, 'decode'):  # pragma: no branch
        exception = None
        encodings = [encoding, 'utf-8', 'cp852', 'iso8859-15', 'latin1']

        for enc in encodings:  # pragma: no cover
            if not enc:
                continue

            try:
                data = data.decode(enc)
                break
            except UnicodeDecodeError as e:
                exception = e
            except UnicodeEncodeError:
                break
        else:  # pragma: no cover
            assert exception is not None
            raise exception  # pragma: no cover

    assert isinstance(data, str)
    return data


def parse(
    src: Source,
    encoding: str | None = None,
    processors: Processors | None = None,
    tags: dict[int | str, mt940.tags.Tag] | None = None,
    transaction_boundary: Iterable[str] | None = None,
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

    Returns:
        The parsed collection of transactions.
    """
    data = _read(src, encoding)
    transactions = mt940.models.Transactions(
        processors, tags, transaction_boundary=transaction_boundary
    )
    transactions.parse(data)

    return transactions


def parse_statements(
    src: Source,
    encoding: str | None = None,
    processors: Processors | None = None,
    tags: dict[int | str, mt940.tags.Tag] | None = None,
    transaction_boundary: Iterable[str] | None = None,
) -> list[Transactions]:
    """
    Parse an mt940 file that contains multiple statement blocks.

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
            processors, tags, transaction_boundary=transaction_boundary
        )
        transactions.parse(block)
        statements.append(transactions)

    return statements
