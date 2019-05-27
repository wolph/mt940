import os
import json
import yaml
import mt940
import pytest
import decimal
import logging
import datetime

from mt940 import _compat


logger = logging.getLogger(__name__)


try:  # pragma: no cover
    string_type = unicode
except NameError:
    string_type = str


def get_sta_files():
    base_path = os.path.relpath(os.path.dirname(__file__))
    for path, dirs, files in os.walk(base_path):
        for file in files:
            _, ext = os.path.splitext(file)
            if ext.lower() == '.sta':
                yield os.path.join(path, file)


def get_yaml_data(sta_file):
    yml_file = sta_file.replace('.sta', '.yml')
    with open(yml_file) as fh:
        return yaml.load(fh, Loader=yaml.Loader)


def write_yaml_data(sta_file, data):
    yml_file = sta_file.replace('.sta', '.yml')
    with open(yml_file, 'w') as fh:
        fh.write(yaml.dump(data, Dumper=yaml.Dumper))


def compare(a, b, key=''):
    if key:
        keys = [key]
    else:
        keys = []

    simple_types = (
        datetime.datetime,
        decimal.Decimal,
    ) + _compat.integer_types
    if isinstance(a, simple_types):
        assert a == b
    elif isinstance(a, _compat.string_types):
        if _compat.PY2:
            if not isinstance(a, _compat.text_type):
                a = a.decode('utf-8', 'replace')

            if not isinstance(b, _compat.text_type):
                b = b.decode('utf-8', 'replace')

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
    # To update the yaml files after changing the code use the following
    # environment variable.
    # NOTE: Only for development purposes
    if os.environ.get('WRITE_YAML_FILES'):
        assert not os.environ.get('TRAVIS')
        write_yaml_data(sta_file, transactions)
    expected = get_yaml_data(sta_file)

    assert len(transactions) >= 0
    repr(transactions)
    str(transactions)

    # Test string and representation methods
    for k, v in transactions.data.items():
        string_type(v)
        repr(v)

    # Test string and representation methods
    for transaction in transactions:
        repr(transaction)
        string_type(transaction)

        for k, v in transaction.data.items():
            string_type(v)
            repr(v)

    # Compare transaction data
    compare(expected, transactions)
    # Compare actual transactions
    compare(expected[:], transactions[:])


@pytest.mark.parametrize('sta_file', get_sta_files())
def test_json_dump(sta_file):
    transactions = mt940.parse(sta_file)
    json.dumps(transactions, cls=mt940.JSONEncoder)
