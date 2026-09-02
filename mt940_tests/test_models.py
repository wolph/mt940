import datetime
import decimal
import typing

import mt940
import mt940._types
import pytest


def test_model_repr_uses_the_class_name() -> None:
    assert repr(mt940.models.Model()) == '<Model>'


def test_balance_empty_amount_string_is_stored_as_is() -> None:
    # 5.0.0 stored an empty amount string unchanged, so that stays: it is
    # neither coerced to an Amount nor turned into None.
    balance = mt940.models.Balance(amount='', status='C', currency='EUR')
    assert balance.amount == ''  # noqa: PLC1901 (the exact value matters)
    assert balance.status == 'C'
    assert str(balance) == ' @ None'


def test_amount_without_a_status_is_positive() -> None:
    # 5.0.0 compared the mark to 'D' and None simply did not match.
    amount = mt940.models.Amount('1.00', None, 'EUR')
    assert amount.amount == decimal.Decimal('1.00')
    assert amount.currency == 'EUR'


def test_balance_amount_string_needs_a_status() -> None:
    # An amount string can only be signed when the balance knows its mark.
    with pytest.raises(
        ValueError, match='Cannot create Amount without status'
    ):
        _ = mt940.models.Balance(amount='1,00', status=None)


def test_default_tags_alias_is_deprecated() -> None:
    with pytest.deprecated_call(match='defaultTags is deprecated'):
        deprecated = mt940.models.Transactions.defaultTags()
    assert deprecated == mt940.models.Transactions.default_tags()


def test_equal_amounts_hash_alike() -> None:
    comma = mt940.models.Amount('1,00', 'C', 'EUR')
    dot = mt940.models.Amount('1.00', 'C', 'EUR')
    assert comma == dot
    assert hash(comma) == hash(dot)
    assert len({comma, dot}) == 1


def test_equal_balances_hash_alike() -> None:
    date = mt940.models.Date(2024, 1, 1)
    first = mt940.models.Balance(
        'C', mt940.models.Amount('1,00', 'C', 'EUR'), date
    )
    second = mt940.models.Balance('C', '1.00', date, currency='EUR')
    assert first == second
    assert hash(first) == hash(second)
    assert len({first, second}) == 1


def test_currency_is_none_without_a_signed_amount() -> None:
    transactions = mt940.models.Transactions()
    assert transactions.currency is None

    # A balance that parsed without an amount carries no currency either,
    # and neither does one holding the empty amount string.
    transactions.data['final_opening_balance'] = mt940.models.Balance(
        status='C'
    )
    assert transactions.currency is None
    transactions.data['final_opening_balance'] = mt940.models.Balance('C', '')
    assert transactions.currency is None

    transactions.data['final_opening_balance'] = mt940.models.Balance(
        'C', mt940.models.Amount('1,00', 'C', 'USD')
    )
    assert transactions.currency == 'USD'


class _Duck:
    """Something that is not a Balance but carries a currency."""

    currency: str = 'GBP'


class _DuckWithAmount:
    """Something that is not a Balance but wraps an object with a currency."""

    def __init__(self) -> None:
        self.amount: mt940.models.Amount = mt940.models.Amount(
            '1,00', 'C', 'JPY'
        )


class _DuckWithoutCurrency:
    """Something whose currency attribute is present but not a string."""

    currency: None = None
    amount: mt940.models.Amount = mt940.models.Amount('1,00', 'C', 'JPY')


def _currency_with(balance: object) -> str | None:
    transactions = mt940.models.Transactions()
    transactions.data['opening_balance'] = balance
    return transactions.currency


@pytest.mark.parametrize(
    ('balance', 'expected'),
    [
        (_Duck(), 'GBP'),
        (_DuckWithAmount(), 'JPY'),
        (_DuckWithoutCurrency(), None),
        (object(), None),
    ],
    ids=['currency', 'amount.currency', 'non-string currency', 'nothing'],
)
def test_currency_duck_types_like_5_0_0(
    balance: object, expected: str | None
) -> None:
    # 5.0.0 accepted any object with a currency, or with an amount that has
    # one, in the balance slots. Nothing usable gives None instead of an
    # AttributeError.
    assert _currency_with(balance) == expected


def test_currency_from_a_bare_floor_limit() -> None:
    transactions = mt940.models.Transactions()
    transactions.data['c_floor_limit'] = mt940.models.Amount(
        '1,00', 'C', 'CHF'
    )
    assert transactions.currency == 'CHF'


def test_scope_marker_is_a_subclass_of_both_and_instantiable() -> None:
    # TransactionsAndTransaction exists for issubclass checks on Tag.scope.
    # Building one worked in 5.0.0 (it runs Transactions.__init__), so it
    # still does.
    assert issubclass(
        mt940.models.TransactionsAndTransaction, mt940.models.Transactions
    )
    assert issubclass(
        mt940.models.TransactionsAndTransaction, mt940.models.Transaction
    )
    marker = mt940.models.TransactionsAndTransaction()
    assert isinstance(marker, mt940.models.Transactions)
    assert isinstance(marker, mt940.models.Transaction)
    assert len(marker) == 0


def test_sum_amount_equality_ignores_the_entry_count() -> None:
    # 5.0.0 semantics: SumAmount compares like the Amount it is, so a plain
    # Amount of the same value is equal and so are two totals over a
    # different number of entries. The explicit __eq__ keeps CodeQL's
    # py/missing-equals satisfied without changing that.
    two = mt940.models.SumAmount('10,00', 'C', 'EUR', number=2)
    also_two = mt940.models.SumAmount('10,00', 'C', 'EUR', number=2)
    three = mt940.models.SumAmount('10,00', 'C', 'EUR', number=3)
    plain = mt940.models.Amount('10,00', 'C', 'EUR')
    other = mt940.models.SumAmount('11,00', 'C', 'EUR', number=2)

    assert two == also_two
    assert two == three
    assert two == plain
    assert plain == two
    assert two != other
    assert hash(two) == hash(three) == hash(plain)
    assert len({two, also_two, three, plain}) == 1


def test_fixed_offset_methods_accept_the_dt_keyword() -> None:
    # The tzinfo methods took `dt` as a keyword in 5.0.0.
    offset = mt940.models.FixedOffset(60, 'CET')
    assert offset.utcoffset(dt=None) == datetime.timedelta(minutes=60)
    assert offset.dst(dt=None) == datetime.timedelta(0)
    assert offset.tzname(dt=None) == 'CET'


def test_processors_alias_is_exported_at_runtime() -> None:
    # 5.0.0 exposed the Processors alias on mt940.models.
    assert mt940.models.Processors is mt940._types.Processors


def test_processor_protocol_hints_resolve_at_runtime() -> None:
    # The protocol signatures name no package class, so get_type_hints
    # works without importing anything, as in 5.0.0.
    hints = typing.get_type_hints(mt940._types.PreProcessor.__call__)
    assert hints['transactions'] is typing.Any
    hints = typing.get_type_hints(mt940._types.PostProcessor.__call__)
    assert hints['tag'] is typing.Any


def test_unpickling_state_without_options_gets_the_defaults() -> None:
    # Pickles written by 5.0.0 carry no options attribute.
    state = mt940.models.Transactions().__getstate__()
    del state['options']
    restored = mt940.models.Transactions.__new__(mt940.models.Transactions)
    restored.__setstate__(state)
    assert restored.options == mt940.Options()


@pytest.mark.parametrize(
    ('status', 'options', 'sign'),
    [
        ('D', mt940.Options(), -1),
        ('RC', mt940.Options(), 1),
        ('d', mt940.Options(), 1),
        ('rc', mt940.Options(), 1),
        ('RC', mt940.Options(reversal_sign=True), -1),
        ('d', mt940.Options(case_insensitive_marks=True), -1),
        ('rc', mt940.Options(reversal_sign=True), 1),
        ('rc', mt940.Options.all(), -1),
        ('RD', mt940.Options.all(), 1),
    ],
)
def test_amount_signing_follows_the_options(
    status: str, options: mt940.Options, sign: int
) -> None:
    # 5.0.0 negated a plain D only. Reversals and lowercase marks are signed
    # on request, and a reversed debit stays positive whatever is switched
    # on.
    amount = mt940.models.Amount('1.00', status, 'EUR', options=options)
    assert amount.amount == sign * decimal.Decimal('1.00')
