from __future__ import annotations

import datetime
import decimal
import json
from typing import Any

from . import models


class JSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        """
        Custom JSON encoder for MT940 models.

        Args:
            o: The object to serialize.

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
