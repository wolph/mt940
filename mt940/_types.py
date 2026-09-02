"""Shared type aliases and processor protocols.

These are the precise types used across the public API. The module is a
*leaf*: it imports nothing from the rest of the package, so it never
participates in an import cycle. That is also why the processor protocols
type their ``transactions`` and ``tag`` arguments as :data:`~typing.Any`:
naming the model and tag classes would need an import, and
:func:`typing.get_type_hints` has to resolve these signatures at runtime, as
it did in 5.0.0. The concrete processors in :mod:`mt940.processors` annotate
them precisely.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import IO, Any, Protocol

#: Accepted input for :func:`mt940.parse` and :func:`mt940.parse_statements`:
#: a path, raw ``str``/``bytes`` data, an open file descriptor, or an open
#: binary/text file handle.
Source = str | bytes | os.PathLike[str] | int | IO[str] | IO[bytes]

#: A parsed tag dictionary. Intentionally dynamic: the available keys are
#: tag- and bank-specific, so a precise ``TypedDict`` would misrepresent it.
TagDict = dict[str, Any]


class PreProcessor(Protocol):
    """A callable run *before* a tag value is turned into a model object."""

    def __call__(
        self,
        # Any rather than the model and tag classes: see the module docstring.
        transactions: Any,  # noqa: ANN401
        tag: Any,  # noqa: ANN401
        tag_dict: TagDict,
        /,
        *args: Any,
    ) -> TagDict: ...


class PostProcessor(Protocol):
    """A callable run *after* a tag value is turned into a model object."""

    def __call__(
        self,
        # Any rather than the model and tag classes: see the module docstring.
        transactions: Any,  # noqa: ANN401
        tag: Any,  # noqa: ANN401
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
