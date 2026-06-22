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


class JSONEncoder(json.JSONEncoder):
    """Serialize MT940 model objects to JSON-compatible primitives.

    Dates, datetimes, timedeltas, timezones and decimals are rendered as
    strings; :class:`~mt940.models.Transactions`,
    :class:`~mt940.models.Transaction`, :class:`~mt940.models.Balance` and
    :class:`~mt940.models.Amount` are rendered as their ``data``/``__dict__``
    mappings. Pass it as the ``cls`` argument to :func:`json.dumps`.
    """

    def default(self, o: Any) -> Any:
        """Return a JSON-serializable representation of ``o``.

        Args:
            o: The object to serialize. ``o`` keeps the permissive ``Any`` type
                of the overridden :meth:`json.JSONEncoder.default`.

        Returns:
            The serialized form of the object.
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
        elif isinstance(o, models.Transactions):
            data: dict[str, Any] = o.data.copy()
            data['transactions'] = o.transactions
            return data

        # If an object has a `data` attribute, return that instead of the
        # `__dict__` to prevent loops
        elif hasattr(o, 'data'):
            return o.data

        # Handle types that have a `__dict__` containing the data (doesn't work
        # for classes using `__slots__` such as `datetime`)
        elif isinstance(o, dict_types):
            return o.__dict__

        else:  # pragma: no cover
            return super().default(o)
