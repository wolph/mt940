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


def test_default_grouping_unchanged():
    # Legacy behaviour: the second :20: overwrites the global reference and a
    # single transaction is produced.
    transactions = mt940.parse(DATA)
    assert len(transactions) == 1
    assert transactions[0].data['transaction_reference'] == 'REF2'


def test_transaction_boundary_opt_in_via_parse():
    transactions = mt940.parse(
        DATA, transaction_boundary={'transaction_reference_number'}
    )
    refs = [t.data.get('transaction_reference') for t in transactions]
    assert refs == ['REF1', 'REF2']


def test_transaction_boundary_opt_in_via_transactions():
    transactions = mt940.models.Transactions(
        transaction_boundary={'transaction_reference_number'}
    )
    transactions.parse(DATA)
    assert len(transactions) == 2
