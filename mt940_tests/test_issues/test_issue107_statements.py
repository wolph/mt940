"""Issue #107: balance-only / multi-statement MT940 files.

A single ``mt940.parse()`` merges everything into one ``Transactions`` and
keeps only the last block's statement-level data (balances).
``parse_statements()``
splits the input on ``:20:`` boundaries so each statement block keeps its own
balances. The default ``parse()`` behaviour is unchanged.
"""

from collections.abc import Callable, Iterable, Iterator

import mt940
import pytest

MULTI_BLOCK = """:20:REF1
:25:ACC1
:28:1/1
:60F:C231231EUR100,00
:62F:C231231EUR111,00
-
:20:REF2
:25:ACC2
:28:1/1
:60F:C231231EUR200,00
:62F:C231231EUR222,00
-
"""


def test_multi_block_balance_only_keeps_every_block() -> None:
    statements = mt940.parse_statements(MULTI_BLOCK)
    assert len(statements) == 2
    assert str(statements[0].data['final_opening_balance']).startswith(
        '100.00'
    )
    assert str(statements[0].data['final_closing_balance']).startswith(
        '111.00'
    )
    assert str(statements[1].data['final_opening_balance']).startswith(
        '200.00'
    )
    assert str(statements[1].data['final_closing_balance']).startswith(
        '222.00'
    )


def test_default_parse_unchanged_for_multi_block() -> None:
    # The default parser still merges and keeps only the last block's balance.
    transactions = mt940.parse(MULTI_BLOCK)
    assert len(transactions) == 0
    assert str(transactions.data['final_opening_balance']).startswith('200.00')


def test_single_statement_returns_one() -> None:
    data = """:20:REF
:25:NL00BANK0123456789EUR
:28:1/1
:60F:C231231EUR1000,00
:62F:C231231EUR1500,00
:64:C231231EUR1500,00
-
"""
    statements = mt940.parse_statements(data)
    assert len(statements) == 1
    assert str(statements[0].data['final_opening_balance']).startswith(
        '1000.00'
    )
    assert str(statements[0].data['available_balance']).startswith('1500.00')


def test_abnamro_file_splits_into_statements() -> None:
    # abnamro.sta has two :20: blocks. parse_statements separates them while
    # the default parse() still merges them into one collection.
    path = 'mt940_tests/jejik/abnamro.sta'
    statements = mt940.parse_statements(path)
    assert len(statements) == 2
    assert len(mt940.parse(path)) == 10


def test_kwargs_passed_through_to_each_block() -> None:
    gls = mt940.tags.StatementGLS()
    data = (
        ':20:R\n:25:ACC\n:60F:C220706EUR0,00\n'
        ':61:2207060706DR20,NTRFBIPI-dvT1FzfMqvzF5HaU4oetlH7SGRkonU'
        '//2022070616391534000\n'
        ':86:116?00x\n:62F:C220706EUR0,00\n'
    )
    statements = mt940.parse_statements(data, tags={gls.id: gls})
    assert len(statements) == 1
    transaction = statements[0].transactions[0]
    assert (
        transaction.data['customer_reference']
        == 'BIPI-dvT1FzfMqvzF5HaU4oetlH7SGRkonU'
    )


class CountingBoundary:
    """A boundary iterable that records how often it is iterated."""

    def __init__(self) -> None:
        self.iterations: int = 0

    def __iter__(self) -> Iterator[str]:
        self.iterations += 1
        return iter(('transaction_details',))


BLOCK: str = (
    ':20:REF\n:25:ACC\n:60F:C200101EUR0,00\n'
    ':61:2001010101C5,00NTRFa//b\n'
    ':86:116?00detail\n:62F:C200101EUR5,00\n'
)


# Factories, not values: an iterator built at import time would be exhausted
# after the first run, so a repeated or re-run test would fail for the wrong
# reason.
@pytest.mark.parametrize(
    'make_boundary',
    [
        lambda: ('transaction_details',),
        lambda: 'transaction_details',
        lambda: iter(('transaction_details',)),
        lambda: (slug for slug in ('transaction_details',)),
    ],
    ids=['tuple', 'string', 'iterator', 'generator'],
)
def test_boundary_iterable_applies_to_every_statement(
    make_boundary: Callable[[], Iterable[str]],
) -> None:
    statements: list[mt940.models.Transactions] = mt940.parse_statements(
        BLOCK + BLOCK, transaction_boundary=make_boundary()
    )

    assert [len(statement) for statement in statements] == [2, 2]
    assert all(
        statement.transaction_boundary == frozenset({'transaction_details'})
        for statement in statements
    )


def test_boundary_is_iterated_once_for_all_statements() -> None:
    boundary: CountingBoundary = CountingBoundary()
    statements: list[mt940.models.Transactions] = mt940.parse_statements(
        BLOCK * 3, transaction_boundary=boundary
    )

    assert [len(statement) for statement in statements] == [2, 2, 2]
    assert boundary.iterations == 1


def test_boundary_untouched_without_statement_blocks() -> None:
    # Pre-5.1 behaviour: input without a :20: block never touches the
    # boundary, so an iterable with side effects sees no iteration at all.
    boundary: CountingBoundary = CountingBoundary()
    statements: list[mt940.models.Transactions] = mt940.parse_statements(
        ':25:ACC\n', transaction_boundary=boundary
    )

    assert statements == []
    assert boundary.iterations == 0
