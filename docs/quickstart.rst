Parse your first statement
==========================

Install the package in your project's virtual environment:

.. code-block:: console

   uv pip install mt-940

The package requires Python 3.10 or newer. If you need an environment first,
:doc:`installation` has the setup commands.

Read one debit
--------------

The following statement uses fictional account and reference values. Enter
this complete example in Python:

.. doctest::

   >>> import mt940
   >>> source: str = """:20:EXAMPLE-001
   ... :25:EXAMPLE-ACCOUNT
   ... :28C:1/1
   ... :60F:C260101EUR100,00
   ... :61:2601020102D12,50NTRFCOFFEE//BANK-001
   ... :86:Coffee supplies
   ... :62F:C260102EUR87,50
   ... """
   >>> statement: mt940.models.Transactions = mt940.parse(source)
   >>> len(statement)
   1
   >>> transaction: mt940.models.Transaction = statement[0]
   >>> print(transaction.data['date'], transaction.data['amount'])
   2026-01-02 -12.50 EUR
   >>> print(statement.data['final_closing_balance'])
   87.50 EUR @ 2026-01-02

``:20:`` supplies the statement reference, ``:25:`` identifies the account and
``:28C:`` gives the statement and sequence numbers. ``:60F:`` supplies the
opening balance. The ``D`` mark on ``:61:`` makes the transaction amount
negative. ``:86:`` supplies its description, and ``:62F:`` supplies the closing
balance. The parser reads that balance directly from the statement.

Read fields and decimal values
------------------------------

A collection has statement metadata in ``data`` and supports indexing and
iteration over transactions. Each transaction has its own ``data`` dictionary:

.. doctest::

   >>> statement.data['account_identification']
   'EXAMPLE-ACCOUNT'
   >>> transaction.data['transaction_details']
   'Coffee supplies'
   >>> amount: mt940.models.Amount = transaction.data['amount']
   >>> amount.amount
   Decimal('-12.50')
   >>> amount.currency
   'EUR'
   >>> transaction.data.get('applicant_iban') is None
   True

The amount is a :class:`decimal.Decimal`, so there is no intermediate float.
The plain description supplies no applicant IBAN. ``get`` handles that missing
field, while a direct lookup would raise ``KeyError``. For fields your
application requires, validate their presence and type before using them.

Run the larger example
----------------------

From a development checkout, the following fixture adds a credit. Every value
is synthetic:

.. literalinclude:: ../examples/fixtures/statement.sta
   :language: text

Run ``uv run python -m examples.basic``. The complete tested implementation is:

.. literalinclude:: ../examples/basic.py
   :language: python

Its recorded output is:

.. literalinclude:: ../examples/output/basic.txt
   :language: text

The two signed movements total ``12.50``. Adding that total to the supplied
opening balance gives the supplied closing balance, so this example prints
``Reconciled: True``. Reconciliation is application code in the example.
The library does not reject a statement whose balances disagree.

Use :doc:`inputs` for paths, byte decoding and streams. :doc:`data-model`
explains the remaining fields and their limits.
