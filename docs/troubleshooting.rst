Diagnose unexpected output
==========================

Start with the smallest synthetic input that preserves the failure. Check its
source type and decoded text before changing tag patterns or processors.
These diagnostics run without a bank file.

An empty collection
-------------------

A filename string that does not identify an existing regular file is treated
as statement text. An unrecognised string can therefore parse without raising:

.. doctest::

   >>> import mt940
   >>> result: mt940.models.Transactions = mt940.parse('not statement content')
   >>> len(result), result.data
   (0, {})
   >>> result = mt940.parse(':20:BALANCES\n:60F:C260101EUR100,00')
   >>> len(result), sorted(result.data)
   (0, ['final_opening_balance', 'transaction_reference'])

The first source has no recognised fields. The second is a valid balance-only
collection. Use ``Path('statement.sta')`` when a file is required, then inspect
both ``len(result)`` and the required metadata. A missing ``Path`` raises
``FileNotFoundError`` instead of becoming inline text.

The first reference is missing
------------------------------

A leading byte-order mark hides an initial tag in default mode:

.. doctest::

   >>> source: str = '\ufeff:20:EXAMPLE'
   >>> mt940.parse(source).data
   {}
   >>> mt940.parse(source, options=mt940.Options(strip_bom=True)).data
   {'transaction_reference': 'EXAMPLE'}

The option applies to the high-level reader. Calling
``Transactions.parse(source)`` directly skips it. Indented markers and tags
embedded in other text also need inspection because tags normally start at
physical line beginnings.

The amount has the wrong sign
-----------------------------

Check the source status mark and selected options:

.. doctest::

   >>> source = ':20:EXAMPLE\n:60F:C260101EUR100,00\n:61:260102rc12,50NTRFREF'
   >>> original: mt940.models.Transactions = mt940.parse(source)
   >>> original[0].data['status'], str(original[0].data['amount'])
   ('rc', '12.50 EUR')
   >>> corrected: mt940.models.Transactions = mt940.parse(
   ...     source,
   ...     options=mt940.Options(reversal_sign=True, case_insensitive_marks=True),
   ... )
   >>> str(corrected[0].data['amount'])
   '-12.50 EUR'

Lowercase reversal-of-credit needs both switches. An application that changed
decimal precision can also round a value during negation. :doc:`data-model`
shows a context diagnostic, and :doc:`compatibility` lists the exact effects.

The currency is ``None``
------------------------

Currency is resolved when the statement line is converted. A balance read
later does not update earlier amounts:

.. doctest::

   >>> late: mt940.models.Transactions = mt940.parse(
   ...     ':20:EXAMPLE\n:61:260102D12,50NTRFREF\n:62F:C260102EUR87,50'
   ... )
   >>> late.currency, late[0].data['amount'].currency
   ('EUR', None)
   >>> supplied: mt940.models.Transactions = mt940.parse(
   ...     ':20:EXAMPLE\n:61:260102D12,50NTRFREF',
   ...     processors={
   ...         'pre_statement': [
   ...             *mt940.models.Transactions.DEFAULT_PROCESSORS['pre_statement'],
   ...             mt940.processors.add_currency_pre_processor('EUR'),
   ...         ],
   ...     },
   ... )
   >>> supplied[0].data['amount'].currency
   'EUR'

Supply a currency only when your source contract establishes it. The new
processor list retains default date fixup. A blank ``:34F:`` mark is another
possible cause, addressed by ``floor_limit_blank_mark``.

A reference or description disappeared
--------------------------------------

Structured ``:86:`` decoding replaces raw ``transaction_details`` with mapped
fields. GVC decoding can also emit ``customer_reference=None`` and replace a
reference read from ``:61:``. Inspect the complete field names:

.. doctest::

   >>> source = ':20:EXAMPLE\n:61:260102C1,00NTRFREF\n:86:105?20SVWZ+Invoice'
   >>> details: mt940.models.Transactions = mt940.parse(source)
   >>> 'transaction_details' in details[0].data, details[0].data['purpose']
   (False, 'Invoice')
   >>> details[0].data['customer_reference'] is None
   True
   >>> kept: mt940.models.Transactions = mt940.parse(
   ...     source, options=mt940.Options(merge_keeps_values=True)
   ... )
   >>> kept[0].data['customer_reference']
   'REF'

The ``merge_keeps_values`` switch protects an existing field from incoming
``None``. It does not preserve raw structured text or free text before genuine
GVC keywords. ``unbounded_details`` removes the legacy capture cap, but later
processors can still discard text. Keep the source alongside parsed data if
you need an exact original record.

There are fewer transactions or balances than expected
------------------------------------------------------

Inspect ``id`` on ``:61:`` results. A trailing transaction without a truthy
``id`` can be reused by the next statement line. A transaction-scoped ``:86:``
before any transaction is dropped. Extra transaction boundaries can create
placeholders, which the next statement line can fill.

For multiple ``:20:`` blocks, use ``parse_statements`` to preserve each
statement's metadata. It does not split ``:28C:`` pages. Repeated intermediate
balance keys overwrite earlier page values. :doc:`statements` covers both
cases and the expected-failure test that records the page-balance limit.

A tag raises an exception
-------------------------

A recognised tag whose text does not match its pattern raises ``RuntimeError``.
Invalid dates can raise ``ValueError`` and invalid decimal text can raise
``decimal.InvalidOperation``. Bare ``:90:`` raises ``AttributeError`` because
the base summary tag has no status. Use the source's debit or credit summary
form, ``:90D:`` or ``:90C:``.

Unknown markers can remain inside a preceding known value because only
registered markers delimit it. Compare the failing value with the tag's
pattern in :mod:`mt940.tags`. Select ``StatementASNB`` or ``StatementGLS`` only
when its documented format matches the bank's line. For a new variant, add a
small synthetic fixture and an isolated override as in :doc:`customising`.

Errors from custom readers, tags and callbacks propagate. Parsing an existing
collection is not atomic. Retry with a fresh collection after correcting the
source or configuration. A report for maintainers should include Python and
package versions, source encoding, selected options, custom callbacks, the
small fixture, actual output and expected output. Do not include live account
numbers, customer names or authentication details.
