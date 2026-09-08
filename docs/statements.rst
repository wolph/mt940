Keep separate statements and group transactions
===============================================

A file can contain several bank statements. If their account numbers,
references and balances must survive separately, use
:func:`mt940.parse_statements`. It returns one
:class:`mt940.models.Transactions` per ``:20:`` block in source order.

Two statements in one file
--------------------------

This fixture contains two fictional statement references with their own
opening and closing balances:

.. literalinclude:: ../examples/fixtures/statements.sta
   :language: text

Run ``uv run python -m examples.statements`` from the checkout:

.. literalinclude:: ../examples/statements.py
   :language: python

The recorded output shows both collections and then the merged form:

.. literalinclude:: ../examples/output/statements.txt
   :language: text

Separate parsing retains the opening balance of ``100.00`` on the first
statement and ``87.50`` on the second. ``parse`` puts both transactions in one
collection and keeps the final value for each repeated metadata key, including
``EXAMPLE-002`` as its reference. A metadata key absent from the final block
can still retain an earlier value.

What creates a statement
------------------------

Only ``:20:`` at the beginning of a physical line splits the input. A header
before the first usable block is discarded. Empty input or input without a
usable ``:20:`` block returns an empty list. A block with balances and no
transactions still produces a collection:

.. doctest::

   >>> import mt940
   >>> blocks: list[mt940.models.Transactions] = mt940.parse_statements(
   ...     ':20:BALANCES-ONLY\n:60F:C260101EUR100,00\n:62F:C260102EUR100,00'
   ... )
   >>> len(blocks), len(blocks[0])
   (1, 0)
   >>> print(blocks[0].data['final_closing_balance'])
   100.00 EUR @ 2026-01-02

``:28C:`` statement and sequence numbers do not split collections. A file with
one ``:20:`` and several pages remains one statement. Repeated ``:60M:`` and
``:62M:`` values overwrite the earlier intermediate balances under their
respective keys. The first-intermediate-balance regression test remains a
strict expected failure. There is no option that retains every page balance.
If page balances are required, retain the original input and implement an
explicit bank-specific page model or processor.

When ``:20:`` marks a transaction
---------------------------------

Some exports use a reference tag to begin a transaction block inside one
statement. Pass tag slugs through ``transaction_boundary`` when that is the
bank's convention:

.. doctest::

   >>> source: str = ':20:FIRST\n:86:First detail\n:20:SECOND\n:86:Second detail'
   >>> grouped: mt940.models.Transactions = mt940.parse(
   ...     source, transaction_boundary={'transaction_reference_number'}
   ... )
   >>> [item.data['transaction_reference'] for item in grouped]
   ['FIRST', 'SECOND']
   >>> grouped[0].data['transaction_details']
   'First detail'

Each configured slug creates a placeholder transaction. A following ``:61:``
can fill that placeholder. The reference also remains in statement metadata
because its tag is statement-scoped. A bare string is accepted as one slug,
and other iterables are materialised once into a frozen set.

Use ``parse`` for this convention. Combining ``parse_statements`` with the
reference boundary also creates a placeholder at every statement opening,
which may be unwanted when the block has no ``:61:`` line.

Default ``:61:`` grouping has another compatibility limit: a trailing
transaction with a missing or false ``id`` is reused. Two ``:61:`` lines without
transaction-type IDs can therefore merge. The parser does not promise one
transaction per physical ``:61:`` under all inputs. Inspect ``id`` and use a
bank-specific adaptation when necessary. See
:meth:`mt940.models.Transactions._process_statement_tag` for the exact rule.
