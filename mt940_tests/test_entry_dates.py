import datetime

import mt940


def _statement(
    transactions: mt940.models.Transactions, **kwargs: object
) -> dict:
    statement = mt940.tags.Statement()
    data = dict(amount='123', status='D', **kwargs)
    return statement(transactions, data)


def test_entry_dates_wrapping_years() -> None:
    transactions = mt940.models.Transactions()

    # Regular statement without an entry date: only the value date is set.
    regular = _statement(transactions, year=2000, month=1, day=1)
    assert regular['date'] == datetime.date(2000, 1, 1)
    assert 'entry_date' not in regular

    # Entry date in the same year as the value date: no correction applied.
    same_year = _statement(
        transactions, year=2000, month=6, day=15, entry_month=6, entry_day=10
    )
    assert same_year['date'] == datetime.date(2000, 6, 15)
    assert same_year['entry_date'] == datetime.date(2000, 6, 10)
    assert same_year['guessed_entry_date'] == same_year['entry_date']

    # Entry date wraps into the next year (value date Dec, entry date Jan).
    forward = _statement(
        transactions, year=2000, month=12, day=31, entry_month=1, entry_day=1
    )
    assert forward['date'] == datetime.date(2000, 12, 31)
    assert forward['entry_date'] == datetime.date(2001, 1, 1)
    assert forward['guessed_entry_date'] == forward['entry_date']

    # Entry date wraps into the previous year (value date Jan, entry date
    # Dec) -- issue #121. `entry_date` must be resolved, not left in the
    # value date's year.
    backward = _statement(
        transactions, year=2000, month=1, day=1, entry_month=12, entry_day=31
    )
    assert backward['date'] == datetime.date(2000, 1, 1)
    assert backward['entry_date'] == datetime.date(1999, 12, 31)
    assert backward['guessed_entry_date'] == backward['entry_date']
