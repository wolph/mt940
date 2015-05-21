import os
import mt940
import pytest


def get_sta_files():
    base_path = os.path.abspath(os.path.dirname(__file__))
    for path, dirs, files in os.walk(base_path):
        for file in files:
            _, ext = os.path.splitext(file)
            if ext.lower() == '.sta':
                yield os.path.join(path, file)


@pytest.mark.parametrize('input', get_sta_files())
def test_parse(input):
    transactions = mt940.parse(input)
    assert len(transactions) >= 0
    repr(transactions)
    str(transactions)

    for k, v in transactions.data.iteritems():
        str(v)
        repr(v)

    for transaction in transactions:
        repr(transaction)
        str(transaction)

        for k, v in transaction.data.iteritems():
            str(v)
            repr(v)
