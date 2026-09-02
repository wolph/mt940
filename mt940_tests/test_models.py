import pytest
from mt940 import models


def test_model_repr_uses_the_class_name() -> None:
    assert repr(models.Model()) == '<Model>'


def test_balance_empty_amount_string_is_none() -> None:
    # A malformed :60F: may carry no amount at all. That is a missing value,
    # not an empty string and not an error.
    balance = models.Balance(amount='', status='C', currency='EUR')
    assert balance.amount is None
    assert balance.status == 'C'


def test_balance_amount_string_needs_a_status() -> None:
    # An amount string can only be signed when the balance knows its mark.
    with pytest.raises(
        ValueError, match='Cannot create Amount without status'
    ):
        _ = models.Balance(amount='1,00', status=None)


def test_default_tags_alias_is_deprecated() -> None:
    with pytest.deprecated_call(match='defaultTags is deprecated'):
        deprecated = models.Transactions.defaultTags()
    assert deprecated == models.Transactions.default_tags()


def test_equal_amounts_hash_alike() -> None:
    comma = models.Amount('1,00', 'C', 'EUR')
    dot = models.Amount('1.00', 'C', 'EUR')
    assert comma == dot
    assert hash(comma) == hash(dot)
    assert len({comma, dot}) == 1


def test_equal_balances_hash_alike() -> None:
    date = models.Date(2024, 1, 1)
    first = models.Balance('C', models.Amount('1,00', 'C', 'EUR'), date)
    second = models.Balance('C', '1.00', date, currency='EUR')
    assert first == second
    assert hash(first) == hash(second)
    assert len({first, second}) == 1


def test_currency_is_none_without_a_signed_amount() -> None:
    transactions = models.Transactions()
    assert transactions.currency is None

    # A balance that parsed without an amount carries no currency either.
    transactions.data['final_opening_balance'] = models.Balance(status='C')
    assert transactions.currency is None

    transactions.data['final_opening_balance'] = models.Balance(
        'C', models.Amount('1,00', 'C', 'USD')
    )
    assert transactions.currency == 'USD'


def test_currency_from_a_bare_floor_limit() -> None:
    transactions = models.Transactions()
    transactions.data['c_floor_limit'] = models.Amount('1,00', 'C', 'CHF')
    assert transactions.currency == 'CHF'


def test_scope_marker_cannot_be_instantiated() -> None:
    # TransactionsAndTransaction only exists for issubclass checks on
    # Tag.scope, so building one is a programming error.
    with pytest.raises(TypeError, match='scope marker'):
        _ = models.TransactionsAndTransaction()
    assert issubclass(models.TransactionsAndTransaction, models.Transactions)
    assert issubclass(models.TransactionsAndTransaction, models.Transaction)


def test_sum_amount_equality_includes_the_entry_count() -> None:
    # CodeQL py/missing-equals: SumAmount adds `number`, so two totals over
    # a different number of entries must not compare equal.
    two = models.SumAmount('10,00', 'C', 'EUR', number=2)
    also_two = models.SumAmount('10,00', 'C', 'EUR', number=2)
    three = models.SumAmount('10,00', 'C', 'EUR', number=3)
    plain = models.Amount('10,00', 'C', 'EUR')

    assert two == also_two
    assert hash(two) == hash(also_two)
    assert two != three
    assert two != plain
    assert len({two, also_two, three}) == 2
