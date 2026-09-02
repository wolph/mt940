"""Issue #110: opt-in transaction boundaries.

By default only the ``:61:`` statement tag starts a new transaction, so a
statement that repeats the ``:20:`` transaction reference per block collapses
into a single transaction (legacy behaviour, kept for backwards
compatibility). The opt-in ``transaction_boundary`` option lets callers
nominate extra tag slugs that each open a new transaction.
"""

import mt940

DATA = """:20:REF1
:20:REF2
:25:ACC
:60F:C200101EUR0,00
:61:2001010101C5,00NTRFr//b
:86:116?00p
:62F:C200101EUR5,00
"""


def test_default_grouping_unchanged() -> None:
    # Legacy behaviour: the second :20: overwrites the global reference and a
    # single transaction is produced.
    transactions = mt940.parse(DATA)
    assert len(transactions) == 1
    assert transactions[0].data['transaction_reference'] == 'REF2'


def test_transaction_boundary_opt_in_via_parse() -> None:
    transactions = mt940.parse(
        DATA, transaction_boundary={'transaction_reference_number'}
    )
    refs = [t.data.get('transaction_reference') for t in transactions]
    assert refs == ['REF1', 'REF2']


def test_transaction_boundary_opt_in_via_transactions() -> None:
    transactions = mt940.models.Transactions(
        transaction_boundary={'transaction_reference_number'}
    )
    transactions.parse(DATA)
    assert len(transactions) == 2


def test_transaction_boundary_accepts_a_bare_string() -> None:
    # A single slug passed as a plain string must not be iterated per-char.
    transactions = mt940.parse(
        DATA, transaction_boundary='transaction_reference_number'
    )
    refs = [t.data.get('transaction_reference') for t in transactions]
    assert refs == ['REF1', 'REF2']


def test_reference_propagates_to_later_statements_in_block() -> None:
    # A block with one :20: and several :61: tags: every transaction in the
    # block must carry the block's reference (the global reference is kept in
    # sync for the transactions_to_transaction post-processor).
    data = """:20:REF1
:61:2001010101C5,00NTRFa//b
:86:116?00p1
:61:2001020102C6,00NTRFc//d
:86:116?00p2
:20:REF2
:61:2001030103C7,00NTRFe//f
:62F:C200101EUR18,00
"""
    transactions = mt940.parse(
        data, transaction_boundary={'transaction_reference_number'}
    )
    refs = [t.data.get('transaction_reference') for t in transactions]
    assert refs == ['REF1', 'REF1', 'REF2']


def test_transaction_scoped_boundary_tag() -> None:
    # A boundary tag whose scope is Transaction (not Transactions) opens a new
    # transaction without touching the global statement data.
    data = """:20:REF
:25:ACC
:60F:C200101EUR0,00
:61:2001010101C5,00NTRFa//b
:86:116?00detail
:62F:C200101EUR5,00
"""
    transactions = mt940.parse(
        data, transaction_boundary={'transaction_details'}
    )
    # The :86: detail tag now opens its own transaction.
    assert len(transactions) == 2
