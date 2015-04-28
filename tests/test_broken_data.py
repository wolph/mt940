import mt940
import pytest


def test_incorrect_transaction_data():
    transaction = mt940.parser.Transaction()

    with pytest.raises(RuntimeError):
        mt940.parser.Transaction(
            transaction=transaction,
            data='foo',
            details='bar',
        )
