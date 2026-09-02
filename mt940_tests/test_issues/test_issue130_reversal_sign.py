"""Issue #130: the ``:61:`` reversal-of-credit mark and its sign.

Field 61 defines four debit/credit marks, not two: ``C``, ``D``, ``RC`` (a
reversal of a credit) and ``RD`` (a reversal of a debit). A reversal of a
credit takes the money back out of the account, so it belongs on the debit
side. A reversal of a debit puts it back in.

Release 5.0.0 negated a plain ``D`` only, so ``RC`` came back positive, and
that stays the default: nothing changes on upgrade. Opt in with
``Options(reversal_sign=True)``. Lowercase marks are a separate switch,
``Options(case_insensitive_marks=True)``.
"""

import decimal
import pathlib

import mt940
import pytest

BETTERPLACE = (
    pathlib.Path(__file__).resolve().parent.parent
    / 'betterplace'
    / 'sepa_mt9401.sta'
)
LEGACY = mt940.Options()
FIXED = mt940.Options.all()


def statement(mark: str) -> str:
    return f""":20:REF
:25:ACC
:60F:C200101EUR0,00
:61:2001010101{mark}5,00NTRFa//b
:86:116?00detail
"""


@pytest.mark.parametrize(
    ('mark', 'legacy', 'fixed'),
    [
        ('C', '5.00', '5.00'),
        ('D', '-5.00', '-5.00'),
        # A reversed credit is money leaving the account.
        ('RC', '5.00', '-5.00'),
        # A reversed debit is money coming back in.
        ('RD', '5.00', '5.00'),
        # The tag patterns compile with re.IGNORECASE, so a lowercase mark
        # parses. 5.0.0 never signed it.
        ('rc', '5.00', '-5.00'),
        ('d', '5.00', '-5.00'),
    ],
)
def test_reversal_marks_default_and_opt_in(
    mark: str, legacy: str, fixed: str
) -> None:
    for options, expected in ((LEGACY, legacy), (FIXED, fixed)):
        transactions = mt940.parse(statement(mark), options=options)
        assert len(transactions) == 1
        transaction = transactions[0]
        assert transaction.data['status'] == mark
        assert transaction.data['amount'].amount == decimal.Decimal(expected)


@pytest.mark.parametrize(
    ('options', 'expected'),
    [(LEGACY, '204.88'), (FIXED, '-204.88')],
)
def test_reversed_credits_in_the_betterplace_statement(
    options: mt940.Options, expected: str
) -> None:
    # This file ships with the library and carries two RC entries of 204,88.
    reversals = [
        transaction
        for transaction in mt940.parse(BETTERPLACE, options=options)
        if transaction.data['status'] == 'RC'
    ]
    assert len(reversals) == 2
    for transaction in reversals:
        assert transaction.data['amount'].amount == decimal.Decimal(expected)


@pytest.mark.parametrize(
    ('options', 'expected_mismatches'),
    [(LEGACY, 2), (FIXED, 0)],
)
def test_betterplace_statements_against_their_own_closing_balance(
    options: mt940.Options, expected_mismatches: int
) -> None:
    # The bank states its own opening and closing balance in :60F: and :62F:,
    # so the entries in between have to add up to the difference. This is the
    # arithmetic that the 5.0.0 sign breaks: the two statements holding a
    # reversal each compute a closing balance 409,76 HIGHER than the one the
    # bank states, which is twice the 204,88 that is counted as arriving
    # instead of leaving.
    #
    # parse_statements rather than parse, because parse merges every block of
    # the file into one Transactions and keeps only the last pair of balances.
    checked = 0
    mismatches = 0

    for transactions in mt940.parse_statements(BETTERPLACE, options=options):
        opening = transactions.data.get('final_opening_balance')
        closing = transactions.data.get('final_closing_balance')
        if opening is None or closing is None:
            continue
        assert isinstance(opening.amount, mt940.models.Amount)
        assert isinstance(closing.amount, mt940.models.Amount)

        total = sum(
            (
                transaction.data['amount'].amount
                for transaction in transactions
            ),
            decimal.Decimal(0),
        )
        if opening.amount.amount + total != closing.amount.amount:
            mismatches += 1
        checked += 1

    # Pinned so the test cannot quietly become vacuous if the file or the
    # splitting changes.
    assert checked == 15
    assert mismatches == expected_mismatches
