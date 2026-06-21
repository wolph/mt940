"""Shared type aliases and processor protocols.

These are the precise types used across the public API. The module is a *leaf*:
it imports nothing from the rest of the package, so it never participates in an
import cycle. The processor protocols therefore type their ``transactions`` and
``tag`` arguments as :data:`~typing.Any`; the concrete processor functions in
:mod:`mt940.processors` still annotate them precisely.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import IO, Any, Protocol

#: Accepted input for :func:`mt940.parse` and :func:`mt940.parse_statements`:
#: a path, raw ``str``/``bytes`` data, or an open binary/text file handle.
Source = str | bytes | os.PathLike[str] | IO[str] | IO[bytes]

#: A parsed tag dictionary. Intentionally dynamic: the available keys are
#: tag- and bank-specific, so a precise ``TypedDict`` would misrepresent it.
TagDict = dict[str, Any]


class PreProcessor(Protocol):
    """A callable run *before* a tag value is turned into a model object."""

    def __call__(
        self,
        transactions: Any,
        tag: Any,
        tag_dict: TagDict,
        /,
        *args: Any,
    ) -> TagDict: ...


class PostProcessor(Protocol):
    """A callable run *after* a tag value is turned into a model object."""

    def __call__(
        self,
        transactions: Any,
        tag: Any,
        tag_dict: TagDict,
        result: TagDict,
        /,
    ) -> TagDict: ...


#: A pre- or post-processor as stored in :attr:`Transactions.processors`.
#: The container mixes both kinds keyed by ``pre_*``/``post_*``, so the element
#: type stays callable-flexible while pinning the return type.
Processor = Callable[..., TagDict]

#: Mapping of processor-slot name to the processors registered for it.
Processors = dict[str, list[Processor]]
