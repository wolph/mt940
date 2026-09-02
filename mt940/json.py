"""JSON serialization for MT940 models.

This module exposes :class:`JSONEncoder`, a :class:`json.JSONEncoder` subclass
that knows how to serialize the model types returned by the parser (balances,
amounts, dates and the transaction collections).

Example:
    >>> import json
    >>> import mt940
    >>> transactions = mt940.models.Transactions()
    >>> json.dumps(transactions, cls=mt940.JSONEncoder)
    '{"transactions": []}'
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
    """Serialize MT940 model objects to JSON-compatible primitives.

    Dates, datetimes, timedeltas, timezones and decimals are rendered as
    strings; :class:`~mt940.models.Transactions`,
    :class:`~mt940.models.Transaction`, :class:`~mt940.models.Balance` and
    :class:`~mt940.models.Amount` are rendered as their ``data``/``__dict__``
    mappings. Pass it as the ``cls`` argument to :func:`json.dumps`.
    """

    def default(self, o: object) -> object:
        """Return a JSON-serializable representation of ``o``.

        Args:
            o: The object to serialize.

        Returns:
            The serialized form of the object. Unsupported types fall through
            to :meth:`json.JSONEncoder.default`, which raises ``TypeError``.
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
