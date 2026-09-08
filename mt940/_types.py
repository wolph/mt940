"""Shared type aliases and processor protocols.

These are the precise types used across the public API. The module is a *leaf*:
it imports nothing from the rest of the package, so it never participates in an
import cycle. That is also why the processor protocols type their
``transactions`` and ``tag`` arguments as :data:`~typing.Any`: naming the model
and tag classes would need an import, and :func:`typing.get_type_hints` has to
resolve these signatures at runtime, as it did in 5.0.0. The concrete
processors in :mod:`mt940.processors` annotate them precisely.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import IO, Any, Protocol

#: Accepted input for :func:`mt940.parse` and :func:`mt940.parse_statements`:
#: a path, raw ``str``/``bytes`` data, an open file descriptor, or an open
#: binary/text file handle.
Source = str | bytes | os.PathLike[str] | int | IO[str] | IO[bytes]

#: Parsed tag fields with dynamic keys determined by the bank and tag.
#: Values may become models or other objects during processing.
TagDict = dict[str, Any]


class PreProcessor(Protocol):
    """Callable that transforms regex groups before model construction.

    The parser calls ``processor(transactions, tag, tag_dict)``. Arguments are
    the active collection, selected tag instance and current group dictionary.
    The callable returns the dictionary supplied to the next pre-processor or
    to the tag. It may mutate that dictionary or replace it with another one.
    Extra positional arguments are supported by the built-in pre-processors for
    compatibility, but the parser supplies only those three arguments.

    Processors run in list order. Exceptions propagate and no mutation is
    rolled back. Avoid assuming raw groups are all strings, since an earlier
    pre-processor may have replaced or converted them.
    """

    def __call__(
        self,
        # Any rather than the model and tag classes: see the module docstring.
        transactions: Any,  # noqa: ANN401
        tag: Any,  # noqa: ANN401
        tag_dict: TagDict,
        /,
        *args: Any,
    ) -> TagDict:
        """Apply the processor contract documented on the owning protocol."""
        ...


class PostProcessor(Protocol):
    """Callable that transforms a tag result before the parser stores it.

    The parser calls ``processor(transactions, tag, tag_dict, result)``. The
    first two arguments identify the collection and tag. ``tag_dict`` is the
    final pre-processed mapping, which the tag may already have mutated.
    ``result`` is the tag's mapping or the preceding post-processor's result.
    Return the mapping to send to the next processor and eventually store.

    Mutation and replacement are both supported. Processors run in list order
    before the current result is stored in statement or transaction data.
    Exceptions propagate without rolling back earlier mutations.
    """

    def __call__(
        self,
        # Any rather than the model and tag classes: see the module docstring.
        transactions: Any,  # noqa: ANN401
        tag: Any,  # noqa: ANN401
        tag_dict: TagDict,
        result: TagDict,
        /,
    ) -> TagDict:
        """Apply the processor contract documented on the owning protocol."""
        ...


#: A pre- or post-processor stored in
#: :attr:`mt940.models.Transactions.processors`.
#: The container mixes both kinds keyed by ``pre_*``/``post_*``, so the element
#: type stays callable-flexible while pinning the return type.
Processor = Callable[..., TagDict]

#: Mapping of processor-slot name to the processors registered for it.
Processors = dict[str, list[Processor]]
