import mt940


def test_entry_dates_wrapping_years():
    transactions = mt940.models.Transactions()
    statement = mt940.tags.Statement()
    data = dict(
        amount='123',
        status='D',
        year=2000,
    )

    # Regular statement
    statement(transactions, dict(
        data.items(),
        month=1,
        day=1,
    ))

    # Statement which wraps to the future
    statement(transactions, dict(
        data.items(),
        month=12,
        day=31,
        entry_day=1,
        entry_month=1,
    ))
    # Statement which wraps the past year
    statement(transactions, dict(
        data.items(),
        month=1,
        day=1,
        entry_day=31,
        entry_month=12,
    ))
