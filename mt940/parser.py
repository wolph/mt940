"""Read paths, handles and raw MT940 text into transaction collections.

Use :func:`parse` when one collection should hold all transactions. Use
:func:`parse_statements` to preserve separate statement metadata in a file
containing several ``:20:`` blocks. Parsing and source reading are synchronous.
Caller-owned handles are read from their current position and stay open.
Passing a numeric file descriptor transfers ownership for that read and closes
it afterwards.
"""

from __future__ import annotations

import os
import pathlib
import re
from typing import TYPE_CHECKING, Protocol, TypeGuard, runtime_checkable

import mt940

from .options import Options

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ._types import Processors, Source
    from .models import Transactions


@runtime_checkable
class _Readable(Protocol):
    """Structural protocol used to recognise an object with a ``read`` method.

    The method takes no arguments and returns text or bytes. Recognition checks
    attribute presence, as in release 5.0.0. It does not validate the method's
    signature or returned value before :func:`_load` calls it.
    """

    def read(self) -> str | bytes:
        """Read remaining source content as text or bytes without arguments."""
        ...


def _decode(data: bytes, encoding: str | None) -> str:
    """Decode bytes with the preferred encoding and the legacy fallbacks.

    A decoding failure tries UTF-8 next, followed by CP852. CP852 maps every
    byte, so malformed input can become readable but incorrect text instead of
    raising ``UnicodeDecodeError``. A successful earlier encoding stops the
    search.

    Args:
        data: Raw statement bytes.
        encoding: First encoding to try. ``None`` or an empty string starts
            with UTF-8. An unknown encoding name does not trigger a fallback.

    Returns:
        Decoded statement text.

    Raises:
        LookupError: The requested encoding name is unknown.
    """
    for enc in (encoding, 'utf-8'):
        if not enc:
            continue
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode('cp852')


def _is_path(
    obj: object,
) -> TypeGuard[str | bytes | os.PathLike[str] | os.PathLike[bytes]]:
    """Recognise the types that can represent paths or inline text.

    This is a type guard, not a filesystem check. Plain text and bytes pass
    even when they contain statement data. :func:`_load` decides whether a file
    exists.

    Args:
        obj: A candidate source.

    Returns:
        Whether ``obj`` is text, bytes or an ``os.PathLike`` object.
    """
    return isinstance(obj, (str, bytes, os.PathLike))


def _load(source: object) -> str | bytes:
    """Read a supported source without decoding it.

    Dispatch checks for a ``read`` method first, then a numeric file
    descriptor, then a string, bytes or path-like object. Text and bytes naming
    an existing regular file are paths. Other text and bytes are inline
    statement data. A path-like object always denotes a file and never becomes
    inline data.

    Args:
        source: A handle, descriptor, path or raw statement data. Handles are
            read once from their current position and left open. Descriptors
            are wrapped in a binary file object and closed after the read.

    Returns:
        Text from a text handle or inline string, otherwise undecoded bytes.

    Raises:
        FileNotFoundError: A path-like object does not name a regular file.
        OSError: Opening or reading a file or descriptor fails.
        TypeError: The source has none of the supported forms.

    Errors from a caller-provided ``read`` method propagate unchanged.
    """
    if isinstance(source, _Readable):
        return source.read()
    if isinstance(source, int):
        # A file descriptor. Reading closes it, as open() did in 5.0.0.
        with open(source, 'rb') as fh:  # noqa: PTH123, FURB101 (a descriptor)
            return fh.read()
    if _is_path(source):
        if os.path.isfile(source):  # noqa: PTH113 (bytes paths are accepted)
            return pathlib.Path(os.fsdecode(source)).read_bytes()
        if isinstance(source, os.PathLike):
            raise FileNotFoundError(os.fsdecode(source))
        return source
    msg = f'unsupported source type {type(source).__name__}'
    raise TypeError(msg)


def _read(
    src: Source,
    encoding: str | None = None,
    *,
    strip_bom: bool = False,
) -> str:
    """Load statement data, decode bytes and optionally remove one BOM.

    Args:
        src: A source accepted by :func:`_load`.
        encoding: First encoding to try for bytes. Ignored for text input.
        strip_bom: Remove one leading U+FEFF after decoding. The default
            preserves the character, which prevents a following ``:20:`` from
            matching the start-of-line tag pattern.

    Returns:
        Statement text. Newlines and whitespace are left for the collection to
        normalise.

    Raises:
        FileNotFoundError: A path-like source does not name a regular file.
        OSError: The source cannot be opened or read.
        TypeError: The source type is unsupported.
        LookupError: A requested encoding name is unknown.
    """
    data = _load(src)
    if isinstance(data, bytes):
        data = _decode(data, encoding)
    if strip_bom:
        data = data.removeprefix('\ufeff')
    return data


def _new_transactions(
    processors: Processors | None,
    tags: dict[int | str, mt940.tags.Tag] | None,
    transaction_boundary: Iterable[str] | None,
    options: Options | None,
) -> Transactions:
    """Build the collection, passing ``options`` only when there are any.

    A :class:`~mt940.models.Transactions` subclass written against 5.0.0 has no
    ``options`` parameter. Leaving the keyword out when it would be ``None``
    anyway keeps such a subclass working through this module.

    Args:
        processors: See :func:`parse`.
        tags: See :func:`parse`.
        transaction_boundary: See :func:`parse`.
        options: See :func:`parse`.

    Returns:
        A fresh, empty collection.
    """
    if options is None:
        return mt940.models.Transactions(
            processors, tags, transaction_boundary=transaction_boundary
        )
    return mt940.models.Transactions(
        processors,
        tags,
        transaction_boundary=transaction_boundary,
        options=options,
    )


def parse(
    src: Source,
    encoding: str | None = None,
    processors: Processors | None = None,
    tags: dict[int | str, mt940.tags.Tag] | None = None,
    transaction_boundary: Iterable[str] | None = None,
    *,
    options: Options | None = None,
) -> Transactions:
    """Parse a source into one collection with statement metadata.

    All recognised tags contribute to the same collection. Later statement tags
    replace earlier values under the same key. Use :func:`parse_statements`
    when separate opening balances, references or account numbers must survive.

    Args:
        src: Raw text or bytes, an existing filename, a path-like object, an
            open text or binary handle, or a numeric file descriptor. Handles
            remain open. Numeric descriptors are closed after reading.
        encoding: First encoding to try for bytes, followed by UTF-8 and CP852.
            Ignored for text. Strings naming existing files are read as paths.
        processors: Processor lists keyed by ``pre_<slug>`` or ``post_<slug>``.
            Each supplied list replaces that slot's default list completely.
            Include default processors explicitly when extending a slot.
        tags: Tag instances keyed by numeric or suffixed tag ID. Entries
            override the corresponding built-in parser or add a new one.
        transaction_boundary: Tag slugs that open transaction blocks in
            addition to statement tags. A bare string means one slug. Empty or
            omitted preserves the default grouping rules.
        options: Immutable opt-in behaviour switches. All ten switches default
            to ``False``. See :class:`mt940.options.Options`.

    Returns:
        A populated :class:`~mt940.models.Transactions`. Empty or unrecognised
        input produces an empty collection.

    Raises:
        FileNotFoundError: A path-like source does not name a regular file.
        OSError: Opening or reading the source fails.
        TypeError: The source type is unsupported.
        LookupError: A requested encoding name is unknown.
        RuntimeError: A recognised tag's value does not match its pattern.
        ValueError: A parsed date or other model value is invalid.
        decimal.InvalidOperation: An amount cannot be converted to a decimal.

    Exceptions raised by custom tags, processors and file handles propagate.
    See :meth:`mt940.models.Transactions.parse` for grouping and mutation
    rules.
    """
    data = _read(src, encoding, strip_bom=(options or Options()).strip_bom)
    transactions = _new_transactions(
        processors, tags, transaction_boundary, options
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
    """Parse each ``:20:`` statement block into a separate collection.

    Only ``:20:`` at the beginning of a physical line splits the input. Content
    before the first usable block is discarded. Whitespace is checked again on
    each block, so a source containing one indented initial ``:20:`` can be
    passed to the collection even though indentation is not a split point.
    Input with no usable ``:20:`` block returns an empty list.

    Each collection has its own metadata, transaction list and tag mapping.
    Processor lists and tag instances remain shared with the supplied mappings,
    as in :func:`parse`. A one-shot boundary iterable is materialised by the
    first collection and reused by later collections.

    Args:
        src: Source accepted by :func:`parse`, read once before splitting.
        encoding: Byte decoding preference, as in :func:`parse`.
        processors: Replacement processor lists applied to every block.
        tags: Extra or overriding tag instances applied to every block.
        transaction_boundary: Additional transaction-start slugs. Selecting
            ``transaction_reference_number`` also creates a placeholder at each
            block's opening reference. Prefer :func:`parse` if ``:20:``
            separates transactions within one statement.
        options: Behaviour switches shared by every collection.

    Returns:
        Collections in source order, including blocks containing balances but
        no transactions. Empty input returns an empty list.

    Raises:
        FileNotFoundError: A path-like source does not name a regular file.
        OSError: Opening or reading the source fails.
        TypeError: The source type is unsupported.
        LookupError: A requested encoding name is unknown.
        RuntimeError: A recognised tag fails to parse in any block.
        ValueError: A parsed model value is invalid.
        decimal.InvalidOperation: A parsed amount is not a valid decimal.

    Other source, tag and processor exceptions propagate as in :func:`parse`.
    No partial list is returned when a later block fails.
    """
    data = _read(src, encoding, strip_bom=(options or Options()).strip_bom)
    statements: list[Transactions] = []
    # Each collection materialises the boundary into a frozenset. Hand the
    # first collection's frozenset to the later ones, so a one-shot iterable
    # (generator, iter(), map()) reaches every statement instead of only the
    # first, and input without any :20: block never touches it.
    boundary: Iterable[str] | None = transaction_boundary
    for block in re.split(r'(?m)^(?=:20:)', data):
        if not block.strip().startswith(':20:'):
            # Drop any leading header / empty chunk before the first :20:.
            continue
        transactions = _new_transactions(processors, tags, boundary, options)
        boundary = transactions.transaction_boundary
        _ = transactions.parse(block)
        statements.append(transactions)

    return statements
