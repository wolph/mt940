"""Serialise MT940 models with the standard :mod:`json` encoder interface.

Dates, amounts and transaction collections contain values that the standard
encoder cannot serialise directly. Pass :class:`JSONEncoder` as ``cls`` to
``json.dumps`` or ``json.dump``. The output preserves decimal precision as
strings and contains no type markers for reconstructing model instances.

Example:
    >>> import json
    >>> import mt940
    >>> json.dumps(mt940.models.Transactions(), cls=mt940.JSONEncoder)
    '{"transactions": []}'
    >>> json.dumps(
    ...     mt940.models.Amount('12,30', 'D', 'EUR'),
    ...     cls=mt940.JSONEncoder,
    ...     sort_keys=True,
    ... )
    '{"amount": "-12.30", "currency": "EUR"}'
"""

from __future__ import annotations

import datetime
import decimal
import json
from typing import Any

from . import models

#: Sentinel for "no ``data`` attribute", so ``data = None`` still counts.
_MISSING = object()


class JSONEncoder(json.JSONEncoder):
    """Convert parser models to dictionaries and lossless decimal strings.

    ``Transactions`` becomes a shallow copy of its metadata with a
    ``transactions`` key containing its transaction list. This key replaces any
    metadata value of the same name. An object exposing ``data`` serialises as
    that attribute, including ``None``. ``Amount`` and ``Balance`` otherwise
    serialise as their instance dictionaries.

    Dates, datetimes, timedeltas, timezones and decimals use ``str``.
    Constructor arguments and JSON formatting controls are inherited from
    :class:`json.JSONEncoder`. Encoding does not mutate parser models.
    """

    def default(self, o: object) -> object:
        """Return a representation that the JSON encoder can visit recursively.

        Args:
            o: An object unsupported by the encoder's native primitive
                handling.

        Returns:
            A string, a model's ``data`` attribute, an amount or balance
            instance dictionary, or copied statement metadata with its
            transaction list.

        Raises:
            TypeError: The object has no supported representation.

        A custom ``data`` attribute is returned as-is. Standard encoder checks
        still apply to its contents, including circular-reference detection.
        """
        # The following types should simply be cast to strings
        str_types = (
            datetime.date,
            datetime.datetime,
            datetime.timedelta,
            datetime.tzinfo,
            decimal.Decimal,
        )

        dict_types = (models.Balance, models.Amount)

        # Handle native types that should be converted to strings
        if isinstance(o, str_types):
            return str(o)

        # Handling of the Transaction objects to include the
        # actual transactions
        if isinstance(o, models.Transactions):
            data: dict[str, Any] = o.data.copy()
            data['transactions'] = o.transactions
            return data

        # If an object has a `data` attribute, return that instead of the
        # `__dict__` to prevent loops
        data_attribute: object = getattr(o, 'data', _MISSING)
        if data_attribute is not _MISSING:
            return data_attribute

        # Handle types that have a `__dict__` containing the data (doesn't work
        # for classes using `__slots__` such as `datetime`)
        if isinstance(o, dict_types):
            return o.__dict__

        return super().default(o)
