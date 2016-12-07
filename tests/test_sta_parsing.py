import os
import yaml
import mt940
import pytest
import decimal
import logging
import datetime

from mt940 import _compat


logger = logging.getLogger(__name__)


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


def write_yaml_data(sta_file, data):
    yml_file = sta_file.replace('.sta', '.yml')
    with open(yml_file, 'w') as fh:
        fh.write(yaml.dump(data))


def compare(a, b, key=''):
    if key:
        keys = [key]
    else:
        keys = []

    simple_types = (
        datetime.datetime,
        decimal.Decimal,
    ) + _compat.string_types + _compat.integer_types
    if isinstance(a, simple_types):
        assert a == b
    elif a is None:
        assert a is b
    elif isinstance(a, dict):
        for k in a:
            assert k in b
            compare(a[k], b[k], '.'.join(keys + [k]))
    elif isinstance(a, (list, tuple)):
        for av, bv in zip(a, b):
            compare(av, bv, key)
    elif hasattr(a, 'data'):
        compare(a.data, b.data, '.'.join(keys + ['data']))
    elif isinstance(a, mt940.models.Model):
        compare(a.__dict__, b.__dict__)
    else:
        raise TypeError('Unsupported type %s' % type(a))


@pytest.mark.parametrize('sta_file', get_sta_files())
def test_parse(sta_file):
    transactions = mt940.parse(sta_file)
    # write_yaml_data(sta_file, transactions)
    expected = get_yaml_data(sta_file)

    assert len(transactions) >= 0
    repr(transactions)
    str(transactions)

    # Test string and representation methods
    for k, v in transactions.data.items():
        str(v)
        repr(v)

    # Test string and representation methods
    for transaction in transactions:
        repr(transaction)
        str(transaction)

        for k, v in transaction.data.items():
            str(v)
            repr(v)

    # Compare transaction data
    compare(transactions, expected)
    # Compare actual transactions
    compare(transactions[:], expected[:])

