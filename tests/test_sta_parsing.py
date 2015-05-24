import os
import yaml
import mt940
import pytest
import decimal


def get_sta_files():
    base_path = os.path.abspath(os.path.dirname(__file__))
    for path, dirs, files in os.walk(base_path):
        for file in files:
            _, ext = os.path.splitext(file)
            if ext.lower() == '.sta':
                yield os.path.join(path, file)


def get_yaml_data(sta_file):
    yml_file = sta_file.replace('.sta', '.yml')
    with open(yml_file) as fh:
        return yaml.load(fh)


def compare(a, b):
    if isinstance(a, (str, int, long, unicode, decimal.Decimal)):
        assert a == b
    elif a is None:
        assert a is b
    elif isinstance(a, dict):
        for k in a:
            compare(a[k], b[k])
    elif isinstance(a, mt940.models.Model):
        compare(a.__dict__, b.__dict__)
    elif hasattr(a, 'data'):
        compare(a.data, b.data)
    else:
        assert a == b

@pytest.mark.parametrize('input', get_sta_files())
def test_parse(input):
    transactions = mt940.parse(input)
    expected = get_yaml_data(input)

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

    compare(transactions, expected)

