=====
Usage
=====

``mt940`` turns raw MT940 statement files into rich Python objects. The
high-level entry point is :func:`mt940.parse`, which accepts a filename, a file
handle, or raw ``str``/``bytes`` and returns a
:class:`mt940.models.Transactions` collection.

Parsing a statement
===================

.. code-block:: python

    import mt940

    transactions = mt940.parse('statement.sta')

    for transaction in transactions:
        print(transaction.data['date'], transaction.data['amount'])

Each :class:`~mt940.models.Transaction` exposes a ``data`` dictionary with the
parsed fields. Which fields are present depends on the source bank and the tags
in the file.

Reading balances
================

Statement-level balances live on the collection's ``data``, not on the
individual transactions. This works even for files that contain no
transactions at all:

.. code-block:: python

    import mt940

    transactions = mt940.parse('statement.sta')
    print(transactions.data['final_opening_balance'])
    print(transactions.data['final_closing_balance'])
    print(transactions.data['available_balance'])

Multiple statements in one file
===============================

A single :func:`mt940.parse` merges everything into one
:class:`~mt940.models.Transactions` and keeps only the **last** block's
statement-level data. For files that concatenate several statements, use
:func:`mt940.parse_statements`, which splits on ``:20:`` boundaries and returns
one collection per statement:

.. code-block:: python

    import mt940

    for statement in mt940.parse_statements('statements.sta'):
        print(statement.data['final_opening_balance'])
        print(statement.data['final_closing_balance'])

Serializing to JSON
===================

:class:`mt940.JSONEncoder` knows how to serialize the model objects:

.. code-block:: python

    import json
    import mt940

    transactions = mt940.parse('statement.sta')
    print(json.dumps(transactions, indent=4, cls=mt940.JSONEncoder))

Opt-in behaviours
=================

Some banks deviate from the SWIFT specification. These behaviours are opt-in so
the defaults stay backwards compatible.

Transaction grouping
--------------------

By default a new transaction is started only on the ``:61:`` statement tag.
Pass ``transaction_boundary`` (an iterable of tag *slugs*) to also start a new
transaction on those tags — for example to treat every ``:20:`` as a boundary:

.. code-block:: python

    import mt940

    transactions = mt940.parse(
        'statement.sta', transaction_boundary={'transaction_reference_number'}
    )

Longer reference fields
-----------------------

Some banks (e.g. GLS / Atruvia) put a customer reference longer than the SWIFT
16-character cap on the ``:61:`` line. Enable the opt-in
:class:`mt940.tags.StatementGLS` tag for those:

.. code-block:: python

    import mt940

    gls = mt940.tags.StatementGLS()
    transactions = mt940.parse('statement.sta', tags={gls.id: gls})

Statements from the Dutch bank ASN
----------------------------------

Tag 61 in ASN statements does not follow the SWIFT specification, so the opt-in
:class:`mt940.tags.StatementASNB` tag is used:

.. code-block:: python

    import mt940

    tag = mt940.tags.StatementASNB()
    transactions = mt940.parse('statement.sta', tags={tag.id: tag})
