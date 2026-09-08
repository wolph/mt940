Customise tags and ordered processors
=====================================

When a bank changes a field format, pass an override to the collection parsing
that export. ``tags`` maps IDs to tag instances. ``processors`` maps named
slots to ordered callback lists. Both high-level parsing functions accept these
arguments.

Add a private tag
-----------------

A tag subclass supplies an ID, scope and regular expression with named groups.
This example assigns a fictional ``:99:`` field to statement metadata:

.. literalinclude:: ../examples/custom_tags.py
   :language: python

Run ``uv run python -m examples.custom_tags``. The recorded result is:

.. literalinclude:: ../examples/output/custom_tags.txt
   :language: text

The class name becomes the slug ``department``. The default tag conversion
returns the captured mapping, giving ``department='OPS'``. The built-in
registry remains unchanged. Its pre/post slot names are ``pre_department`` and
``post_department``.

For a bank's ``:61:`` variant, instantiate :class:`mt940.tags.StatementASNB` or
:class:`mt940.tags.StatementGLS` and pass ``tags={tag.id: tag}``. Registering a
suffixed ID such as ``'60F'`` takes precedence over the numeric base ID ``60``.
The accepted tag marker syntax remains two digits or ``NS``, optionally
followed by one uppercase letter.

Scope controls storage. :class:`mt940.models.Transactions` stores statement
metadata, and :class:`mt940.models.Transaction` stores on the latest transaction.
A transaction-scoped tag before the first transaction is dropped.
:class:`mt940.models.TransactionsAndTransaction` routes to the latest
transaction when present, otherwise to statement metadata. It does not write
to both. ``Statement`` subclasses and configured transaction boundaries have
special grouping rules described in :doc:`statements`.

To change balance scope, create a local subclass of the specific balance tag
and override its ``scope``. Register that instance for the required ID.
Changing ``BalanceBase.scope`` globally or mutating a shared built-in instance
changes unrelated parsing too.

Transform before or after conversion
------------------------------------

The callbacks receive these arguments in order:

.. list-table:: Processor contracts
   :header-rows: 1
   :widths: 25 40 35

   * - Slot
     - Arguments
     - Returned value
   * - ``pre_<slug>``
     - ``transactions, tag, tag_dict``
     - Capture mapping for the next pre-processor or tag conversion.
   * - ``post_<slug>``
     - ``transactions, tag, tag_dict, result``
     - Result mapping for the next post-processor or storage.

Pre-processors run after regex capture but before the tag creates model values.
Post-processors run after conversion and before the current result is stored.
Each return value replaces the mapping passed to the next step. Returning
``None`` is not a way to skip processing. A callback may mutate its input or
return a new dictionary, but it needs to preserve fields required downstream.
Exceptions propagate, and earlier mutations are not rolled back.

This pre-processor returns a replacement mapping before the account is stored:

.. doctest::

   >>> from typing import Any
   >>> import mt940
   >>> def upper_account(
   ...     transactions: mt940.models.Transactions,
   ...     tag: mt940.tags.Tag,
   ...     tag_dict: dict[str, Any],
   ... ) -> dict[str, Any]:
   ...     del transactions, tag
   ...     account: str = tag_dict['account_identification']
   ...     return {**tag_dict, 'account_identification': account.upper()}
   >>> statement: mt940.models.Transactions = mt940.parse(
   ...     ':20:EXAMPLE\n:25:example-account',
   ...     processors={'pre_account_identification': [upper_account]},
   ... )
   >>> statement.data['account_identification']
   'EXAMPLE-ACCOUNT'

Extend a default slot
---------------------

Supplying a slot replaces its entire list. An empty list disables its default
callbacks. To add a callback after the defaults, create a new list:

.. literalinclude:: ../examples/processors.py
   :language: python

Run ``uv run python -m examples.processors``. Its recorded output is:

.. literalinclude:: ../examples/output/processors.txt
   :language: text

The existing details parser runs first. The added callback receives its result
and returns a new mapping containing a category. The original default list
still contains one callback. Appending directly to
``Transactions.DEFAULT_PROCESSORS[slot]`` or to a shared collection slot would
modify other collections using the same list.

Built-in helpers
----------------

:func:`mt940.processors.add_currency_pre_processor` creates a callback that
supplies a currency, with an ``overwrite`` switch controlling replacement.
:func:`mt940.processors.transactions_to_transaction` copies selected statement
fields into transaction results. The default statement slot uses it for the
statement reference.

:func:`mt940.processors.date_fixup_pre_processor` and
:func:`mt940.processors.date_cleanup_post_processor` provide the default
statement date repair and raw-field removal. Replacing their slots removes
those behaviours unless you include them again.

:data:`mt940.processors.transaction_details_post_processor_with_space`
replaces the default structured-details processor when fragments should be
joined with spaces. The mBank callbacks in :mod:`mt940.processors` extract
bank-specific codes and references when explicitly registered.
The :mod:`mt940._types` reference defines the processor protocols.
