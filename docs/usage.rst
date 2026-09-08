Choose a parsing workflow
=========================

Start with :doc:`quickstart` if you have not parsed a statement yet. It contains
a complete input and executed output. The guides below address the choices an
application makes after that first parse.

.. list-table:: Pick the operation
   :header-rows: 1
   :widths: 35 35 30

   * - Input or requirement
     - Entry point
     - Guide
   * - One statement, or intentionally merged metadata
     - :func:`mt940.parse`
     - :doc:`inputs`
   * - Separate statements beginning with ``:20:``
     - :func:`mt940.parse_statements`
     - :doc:`statements`
   * - Amounts, dates, balances and optional fields
     - :class:`mt940.models.Transactions`
     - :doc:`data-model`
   * - JSON for storage or another service
     - :class:`mt940.JSONEncoder`
     - :doc:`json`
   * - A different bank tag or processing rule
     - ``tags`` and ``processors`` arguments
     - :doc:`customising`
   * - Preserve defaults while selecting parsing fixes
     - :class:`mt940.Options`
     - :doc:`compatibility`

A collection returned by ``parse`` can be empty even when its metadata contains
an account or balances. An unrecognised string can also return an empty
collection. Check the fields you require instead of treating an empty
transaction list as a universal parse-failure signal.

Supported bank variants and tag output tables are in :doc:`bank-formats`.
When an expected field is missing or changed, use :doc:`troubleshooting` to
trace the source, tag and processor involved. The generated :doc:`modules`
reference documents exact arguments and exceptions.
