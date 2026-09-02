"""Issue #130: the ``:61:`` reversal marks must carry the right sign.

Field 61 defines four debit/credit marks, not two: ``C``, ``D``, ``RC`` (a
reversal of a credit) and ``RD`` (a reversal of a debit). A reversal of a
credit takes the money back out of the account, so it belongs on the debit
side; a reversal of a debit puts it back in.

``RC`` used to come back positive, which is a silent error: nothing raised,
nothing warned, and the figure that came out was plausible.
"""

import decimal
import os
import pathlib

import mt940
import pytest

BETTERPLACE = os.path.join(
    pathlib.Path(pathlib.Path(pathlib.Path(__file__).resolve()).parent).parent,
    'betterplace',
    'sepa_mt9401.sta',
)


def statement(mark) -> str:
    return f""":20:REF
:25:ACC
:60F:C200101EUR0,00
:61:2001010101{mark}5,00NTRFa//b
:86:116?00detail
"""


@pytest.mark.parametrize(
    ('mark', 'expected'),
    [
        ('C', decimal.Decimal('5.00')),
        ('D', decimal.Decimal('-5.00')),
        # A reversed credit is money leaving the account.
        ('RC', decimal.Decimal('-5.00')),
        # A reversed debit is money coming back in.
        ('RD', decimal.Decimal('5.00')),
        # The tag patterns compile with re.IGNORECASE, so a lowercase mark
        # parses and has to be signed the same way.
        ('rc', decimal.Decimal('-5.00')),
        ('d', decimal.Decimal('-5.00')),
    ],
)
def test_reversal_marks_get_the_sign_of_their_direction(
    mark, expected
) -> None:
    transactions = mt940.parse(statement(mark))
    assert len(transactions) == 1
    transaction = transactions[0]
    assert transaction.data['status'] == mark
    assert transaction.data['amount'].amount == expected


def test_reversed_credits_in_the_betterplace_statement_are_negative() -> None:
    # This file ships with the library and carries two RC entries of 204,88.
    reversals = [
        transaction
        for transaction in mt940.parse(BETTERPLACE)
        if transaction.data['status'] == 'RC'
    ]
    assert len(reversals) == 2
    for transaction in reversals:
        assert transaction.data['amount'].amount == decimal.Decimal('-204.88')


def test_every_betterplace_statement_matches_its_own_closing_balance() -> None:
    # The bank states its own opening and closing balance in :60F: and :62F:,
    # so the entries in between have to add up to the difference. This is the
    # arithmetic that the RC sign used to break: the two statements holding a
    # reversal each computed a closing balance 409,76 HIGHER than the one the
    # bank states, which is twice the 204,88 that was counted as arriving
    # instead of leaving.
    #
    # parse_statements rather than parse, because parse merges every block of
    # the file into one Transactions and keeps only the last pair of balances.
    checked = 0

    for transactions in mt940.parse_statements(BETTERPLACE):
        opening = transactions.data.get('final_opening_balance')
        closing = transactions.data.get('final_closing_balance')
        if opening is None or closing is None:
            continue

        total = sum(
            (
                transaction.data['amount'].amount
                for transaction in transactions
            ),
            decimal.Decimal(0),
        )
        assert opening.amount.amount + total == closing.amount.amount
        checked += 1

    # Pinned so the test cannot quietly become vacuous if the file or the
    # splitting changes.
    assert checked == 15
