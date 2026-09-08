Export a statement to JSON
==========================

Parsed dates and decimal amounts need a representation before another service
can consume them. :class:`mt940.JSONEncoder` supports the standard library's
``json.dump`` and ``json.dumps`` through their ``cls`` argument.

Export every parsed field
-------------------------

Run ``uv run python -m examples.json_export`` from the checkout. It reads the
synthetic fixture shown in :doc:`quickstart`:

.. literalinclude:: ../examples/json_export.py
   :language: python

The entire recorded output is:

.. literalinclude:: ../examples/output/json_export.txt
   :language: json

The outer object contains statement metadata and a ``transactions`` array.
Each array item contains its transaction's ``data``. A balance contains
``status``, ``date`` and a nested amount object. Decimal values such as
``"-12.50"`` are strings, and dates use their string representation.
Missing optional captures can become JSON ``null``. Absent dictionary keys
remain absent.

The encoder has no type markers and no matching model decoder. Loading this
JSON returns ordinary dictionaries, lists, strings and primitive values:

.. doctest::

   >>> import json
   >>> import mt940
   >>> encoded: str = json.dumps(
   ...     mt940.models.Amount('12,50', 'D', 'EUR'), cls=mt940.JSONEncoder
   ... )
   >>> decoded: dict[str, str] = json.loads(encoded)
   >>> type(decoded).__name__, decoded['amount']
   ('dict', '-12.50')

When reconstructing an application amount, use ``Decimal(decoded['amount'])``
and validate your currency field separately. Do not expect ``json.loads`` to
produce an ``Amount`` instance.

An application-owned report
---------------------------

A service often needs a smaller, stable set of fields. This complete example
reads the fixture bytes, parses them, checks required balance and amount types,
checks transaction currencies, reconciles the supplied balances and creates a
report containing standard JSON types:

.. literalinclude:: ../examples/walkthrough.py
   :language: python

Run ``uv run python -m examples.walkthrough``. Its recorded output is:

.. literalinclude:: ../examples/output/walkthrough.txt
   :language: json

The report exposes the fictional account, currency, reconciliation result and
three fields per transaction. Amounts are still decimal strings. The example
uses a deliberately small set of required fields. Extend those checks to your
bank's account identifiers, closing currency and reporting dates before using
the report as an import contract.

Encoder details
---------------

``Transactions`` encoding shallow-copies metadata and then inserts the
``transactions`` array. A metadata key named ``transactions`` is overwritten
in the encoded result. Other objects exposing ``data`` encode as that attribute,
including ``None``. ``Amount`` and ``Balance`` encode their instance attributes,
so extra custom attributes can appear in the output.

Dates, datetimes, timedeltas, timezones and decimals become strings. Unsupported
objects raise ``TypeError`` through the standard encoder. Encoding does not
mutate the parsed collection, but arbitrary custom objects or circular values
inside ``data`` remain subject to the standard JSON encoder's checks.
