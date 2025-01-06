from __future__ import annotations

import datetime
import decimal
import json
import logging
import os
from typing import Any

import mt940
import pytest
import yaml

try:
    from yaml import (
        CDumper as Dumper,
        CLoader as Loader,
    )
except ImportError:
    from yaml import Dumper, Loader


logger = logging.getLogger(__name__)


def get_sta_files():
    base_path = os.path.relpath(os.path.dirname(__file__))
    for path, _dirs, files in os.walk(base_path):
        for file in files:
            _, ext = os.path.splitext(file)
            if ext.lower() == '.sta':
                yield os.path.join(path, file)


def get_yaml_data(sta_file):
    yml_file = sta_file.replace('.sta', '.yml')
    with open(yml_file) as fh:
        return yaml.load(fh, Loader=Loader)


def write_yaml_data(sta_file, data):
    yml_file = sta_file.replace('.sta', '.yml')
    with open(yml_file, 'w') as fh:
        fh.write(yaml.dump(data, Dumper=Dumper))


def compare(a: Any, b: Any, keys: list[str] | None = None) -> None:
    """
    Recursively compares two objects `a` and `b`, asserting their equality.

    Args:
        a: The first object to compare.
        b: The second object to compare.
        keys: A list of strings representing the nested key path being
        compared.

    Raises:
        AssertionError: If `a` and `b` are not equal.
        TypeError: If the type of `a` is not supported for comparison.
    """
    if keys is None:
        keys = []

    if isinstance(a, (datetime.datetime, decimal.Decimal, int)):
        compare_simple_types(a, b, keys)
    elif isinstance(a, str):
        compare_strings(a, b, keys)
    elif a is None:
        compare_none(a, b, keys)
    elif isinstance(a, dict):
        compare_dicts(a, b, keys)
    elif isinstance(a, (list, tuple)):
        compare_iterables(a, b, keys)
    elif hasattr(a, 'data'):
        compare_data_attributes(a, b, keys)
    elif mt940 is not None and isinstance(a, mt940.models.Model):
        compare_model_instances(a, b, keys)
    else:
        path = '.'.join(keys)
        raise TypeError(f'Unsupported type {type(a)} at {path}')


def compare_simple_types(a: Any, b: Any, keys: list[str]) -> None:
    """
    Compare simple types like datetime, Decimal, and int.

    Args:
        a: The first simple type to compare.
        b: The second simple type to compare.
        keys: The key path being compared.

    Raises:
        AssertionError: If `a` and `b` are not equal.
    """
    if a != b:
        path = '.'.join(keys)
        raise AssertionError(f'Difference at {path}: {a} != {b}')


def compare_strings(a: str, b: str, keys: list[str]) -> None:
    """
    Compare string types.

    Args:
        a: The first string to compare.
        b: The second string to compare.
        keys: The key path being compared.

    Raises:
        AssertionError: If `a` and `b` are not equal.
    """
    if a != b:
        path = '.'.join(keys)
        raise AssertionError(f"Difference at {path}: '{a}' != '{b}'")


def compare_none(a: None, b: None, keys: list[str]) -> None:
    """
    Compare None types.

    Args:
        a: The first None value.
        b: The second None value.
        keys: The key path being compared.

    Raises:
        AssertionError: If `a` is not `b`.
    """
    if a is not b:
        path = '.'.join(keys)
        raise AssertionError(f'Difference at {path}: {a} is not {b}')


def compare_dicts(
    a: dict[Any, Any], b: dict[Any, Any], keys: list[str]
) -> None:
    """
    Compare dictionaries recursively.

    Args:
        a: The first dictionary to compare.
        b: The second dictionary to compare.
        keys: The key path being compared.

    Raises:
        AssertionError: If there are differences in keys or values.
    """
    for k in a:
        if k not in b:
            path = '.'.join([*keys, str(k)])
            raise AssertionError(f"Key '{k}' missing in second dict at {path}")
        compare(a[k], b[k], [*keys, str(k)])
    for k in b:
        if k not in a:
            path = '.'.join([*keys, str(k)])
            raise AssertionError(
                f"Unexpected key '{k}' in second dict at {path}"
            )


def compare_iterables(
    a: list[Any] | tuple[Any, ...],
    b: list[Any] | tuple[Any, ...],
    keys: list[str],
) -> None:
    """
    Compare lists or tuples recursively.

    Args:
        a: The first iterable to compare.
        b: The second iterable to compare.
        keys: The key path being compared.

    Raises:
        AssertionError: If there are differences in lengths or elements.
    """
    if len(a) != len(b):
        path = '.'.join(keys)
        raise AssertionError(
            f'Difference in length at {path}: {len(a)} != {len(b)}'
        )
    for index, (av, bv) in enumerate(zip(a, b)):
        compare(av, bv, [*keys, f'[{index}]'])


def compare_data_attributes(a: Any, b: Any, keys: list[str]) -> None:
    """
    Compare objects that have a 'data' attribute.

    Args:
        a: The first object to compare.
        b: The second object to compare.
        keys: The key path being compared.
    """
    compare(a.data, b.data, [*keys, 'data'])


def compare_model_instances(a: Any, b: Any, keys: list[str]) -> None:
    """
    Compare model instances by comparing their __dict__ attributes.

    Args:
        a: The first model instance to compare.
        b: The second model instance to compare.
        keys: The key path being compared.
    """
    compare(a.__dict__, b.__dict__, keys)


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
    for v in transactions.data.values():
        str(v)
        repr(v)

    # Test string and representation methods
    for transaction in transactions:
        repr(transaction)
        str(transaction)

        for v in transaction.data.values():
            str(v)
            repr(v)

    # Compare transaction data
    compare(expected, transactions)
    # Compare actual transactions
    compare(expected[:], transactions[:])


@pytest.mark.parametrize('sta_file', get_sta_files())
def test_json_dump(sta_file):
    transactions = mt940.parse(sta_file)
    json.dumps(transactions, cls=mt940.JSONEncoder)
