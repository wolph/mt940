"""Golden-file tests: every ``.sta`` fixture must parse to its ``.yml`` twin.

Set ``WRITE_YAML_FILES=1`` to regenerate the goldens after an intentional
change to the parser output.
"""

from __future__ import annotations

import datetime
import decimal
import json
import os
import pathlib
import re
from typing import TYPE_CHECKING, NoReturn

import mt940
import pytest
import yaml

if TYPE_CHECKING:
    from typing_extensions import TypeIs

_TESTS_PATH = pathlib.Path(__file__).parent
_SCALAR_TYPES = (datetime.date, decimal.Decimal, int, str)
_DATA_TYPES = (mt940.models.Transactions, mt940.models.Transaction)

_STATEMENT = """:20:REF
:25:ACC
:28C:1
:60F:C231229EUR0,00
:61:2312290101C10,00NTRFREF//BANK
:86:detail
:62F:C231229EUR10,00
"""


def get_sta_files() -> list[str]:
    # Relative paths keep the parametrised test ids short and stable.
    base_path = pathlib.Path(os.path.relpath(_TESTS_PATH))
    return sorted(str(path) for path in base_path.rglob('*.sta'))


#: Every fixture is parsed once per mode. The default mode pins the 5.0.0
#: output, the ``all`` mode pins the output with every opt-in fix enabled.
MODES: dict[str, mt940.Options] = {
    'default': mt940.Options(),
    'all': mt940.Options.all(),
}


def _golden_path(sta_file: str, mode: str = 'default') -> pathlib.Path:
    # ``x.yml`` for the default mode, ``x.<mode>.yml`` for the others.
    suffix = '.yml' if mode == 'default' else f'.{mode}.yml'
    return pathlib.Path(sta_file).with_suffix(suffix)


def get_yaml_data(sta_file: str, mode: str = 'default') -> object:
    path = _golden_path(sta_file, mode)
    if not path.exists():
        # The fixes leave this fixture unchanged, the default golden applies.
        path = _golden_path(sta_file)
    with path.open(encoding='utf-8') as fh:
        # The goldens carry the !!python tags written by write_yaml_data, so
        # only the full Loader can read them back.
        data: object = yaml.load(fh, Loader=yaml.Loader)  # noqa: S506
    return data


def write_yaml_data(
    sta_file: str, data: object, mode: str = 'default'
) -> None:
    _ = _golden_path(sta_file, mode).write_text(
        yaml.dump(data, Dumper=yaml.Dumper), encoding='utf-8'
    )


def _as_json(transactions: mt940.models.Transactions) -> str:
    return json.dumps(transactions, cls=mt940.JSONEncoder, sort_keys=True)


def maybe_write_golden(
    sta_file: str,
    transactions: mt940.models.Transactions,
    mode: str = 'default',
) -> None:
    # Development only: regenerate the golden next to the fixture. A non
    # default mode only gets its own golden when its output differs from the
    # default one, so the fixture tree shows exactly which files the fixes
    # change.
    if not os.environ.get('WRITE_YAML_FILES'):
        return
    if mode != 'default' and _as_json(transactions) == _as_json(
        mt940.parse(sta_file)
    ):
        _golden_path(sta_file, mode).unlink(missing_ok=True)
        return
    write_yaml_data(sta_file, transactions, mode)


def _path(keys: list[str]) -> str:
    return '.'.join(keys) or '<root>'


def _fail_kind_mismatch(a: object, b: object, keys: list[str]) -> NoReturn:
    msg = (
        f'Type mismatch at {_path(keys)}: '
        f'{type(a).__name__} != {type(b).__name__}'
    )
    raise AssertionError(msg)


def _is_dict(value: object) -> TypeIs[dict[object, object]]:
    return isinstance(value, dict)


def _is_sequence(value: object) -> TypeIs[list[object] | tuple[object, ...]]:
    return isinstance(value, (list, tuple))


def compare(a: object, b: object, keys: list[str] | None = None) -> None:
    """Recursively compare ``a`` and ``b``, asserting their equality.

    Args:
        a: The expected object, as loaded from the golden file.
        b: The parsed object.
        keys: The nested key path being compared.

    Raises:
        TypeError: If the type of ``a`` is not supported for comparison.
    """
    if keys is None:
        keys = []

    if a is None or isinstance(a, _SCALAR_TYPES):
        compare_scalars(a, b, keys)
    elif _is_dict(a):
        compare_dicts(a, b, keys)
    elif _is_sequence(a):
        compare_iterables(a, b, keys)
    elif isinstance(a, _DATA_TYPES):
        compare_data_attributes(a, b, keys)
    elif isinstance(a, mt940.models.Model):
        compare_model_instances(a, b, keys)
    else:
        msg = f'Unsupported type {type(a)} at {_path(keys)}'
        raise TypeError(msg)


def compare_scalars(a: object, b: object, keys: list[str]) -> None:
    """Compare two scalars (``None``, dates, decimals, ints and strings).

    Args:
        a: The expected scalar.
        b: The parsed scalar.
        keys: The key path being compared.

    Raises:
        AssertionError: If ``a`` and ``b`` differ.
    """
    if a != b:
        msg = f'Difference at {_path(keys)}: {a!r} != {b!r}'
        raise AssertionError(msg)


def compare_dicts(a: dict[object, object], b: object, keys: list[str]) -> None:
    """Compare dictionaries recursively.

    Args:
        a: The expected dictionary.
        b: The parsed dictionary.
        keys: The key path being compared.

    Raises:
        AssertionError: If the keys or any value differ.
    """
    if not _is_dict(b):
        _fail_kind_mismatch(a, b, keys)
    for key, value in a.items():
        path = [*keys, str(key)]
        if key not in b:
            msg = f'Key {key!r} missing in second dict at {_path(path)}'
            raise AssertionError(msg)
        compare(value, b[key], path)
    for key in b:
        if key not in a:
            path = [*keys, str(key)]
            msg = f'Unexpected key {key!r} in second dict at {_path(path)}'
            raise AssertionError(msg)


def compare_iterables(
    a: list[object] | tuple[object, ...], b: object, keys: list[str]
) -> None:
    """Compare lists or tuples recursively.

    Args:
        a: The expected sequence.
        b: The parsed sequence.
        keys: The key path being compared.

    Raises:
        AssertionError: If the lengths or any element differ.
    """
    if not _is_sequence(b):
        _fail_kind_mismatch(a, b, keys)
    if len(a) != len(b):
        msg = f'Difference in length at {_path(keys)}: {len(a)} != {len(b)}'
        raise AssertionError(msg)
    for index, (av, bv) in enumerate(zip(a, b, strict=True)):
        compare(av, bv, [*keys, f'[{index}]'])


def compare_data_attributes(
    a: mt940.models.Transactions | mt940.models.Transaction,
    b: object,
    keys: list[str],
) -> None:
    """Compare objects through their ``data`` attribute.

    Args:
        a: The expected object.
        b: The parsed object.
        keys: The key path being compared.
    """
    if not isinstance(b, _DATA_TYPES):
        _fail_kind_mismatch(a, b, keys)
    compare(a.data, b.data, [*keys, 'data'])


def compare_model_instances(
    a: mt940.models.Model, b: object, keys: list[str]
) -> None:
    """Compare model instances through their instance attributes.

    Args:
        a: The expected model.
        b: The parsed model.
        keys: The key path being compared.
    """
    if not isinstance(b, mt940.models.Model):
        _fail_kind_mismatch(a, b, keys)
    compare(vars(a), vars(b), keys)


def test_compare_accepts_equal_structures() -> None:
    transactions = mt940.parse(_STATEMENT)
    compare(mt940.parse(_STATEMENT), transactions)
    compare(transactions[:], transactions[:])
    compare(
        {'k': [1, 'a', None, decimal.Decimal('1.5')], 'd': {'n': 1}},
        {'k': (1, 'a', None, decimal.Decimal('1.5')), 'd': {'n': 1}},
    )


@pytest.mark.parametrize(
    ('expected', 'actual', 'message'),
    [
        ('a', 'b', "Difference at <root>: 'a' != 'b'"),
        (None, 1, 'Difference at <root>: None != 1'),
        ({'k': {'j': 1}}, {'k': {'j': 2}}, 'Difference at k.j: 1 != 2'),
        ({'k': 1}, {}, "Key 'k' missing in second dict at k"),
        ({}, {'k': 1}, "Unexpected key 'k' in second dict at k"),
        ([1], [1, 2], 'Difference in length at <root>: 1 != 2'),
        ([1, 2], [1, 3], 'Difference at [1]: 2 != 3'),
        ({'k': 1}, [1], 'Type mismatch at <root>: dict != list'),
        ([1], {'k': 1}, 'Type mismatch at <root>: list != dict'),
        (
            mt940.models.Amount('1', 'C', 'EUR'),
            mt940.models.Amount('2', 'C', 'EUR'),
            "Difference at amount: Decimal('1') != Decimal('2')",
        ),
        (
            mt940.models.Amount('1', 'C', 'EUR'),
            'x',
            'Type mismatch at <root>: Amount != str',
        ),
        (
            mt940.parse(_STATEMENT),
            mt940.parse(_STATEMENT.replace('REF', 'OTHER')),
            "Difference at data.transaction_reference: 'REF' != 'OTHER'",
        ),
        (
            mt940.parse(_STATEMENT),
            {},
            'Type mismatch at <root>: Transactions != dict',
        ),
    ],
)
def test_compare_reports_the_first_difference(
    expected: object, actual: object, message: str
) -> None:
    with pytest.raises(AssertionError, match=re.escape(message)):
        compare(expected, actual)


def test_compare_rejects_unsupported_types() -> None:
    with pytest.raises(TypeError, match='Unsupported type'):
        compare(object(), object())


def test_write_yaml_data_round_trips(tmp_path: pathlib.Path) -> None:
    sta_file = str(tmp_path / 'statement.sta')
    _ = pathlib.Path(sta_file).write_text(_STATEMENT, encoding='utf-8')
    transactions = mt940.parse(sta_file)

    write_yaml_data(sta_file, transactions)

    compare(get_yaml_data(sta_file), transactions)


def test_maybe_write_golden_honours_the_environment(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sta_file = str(tmp_path / 'statement.sta')
    _ = pathlib.Path(sta_file).write_text(_STATEMENT, encoding='utf-8')
    transactions = mt940.parse(sta_file)

    monkeypatch.delenv('WRITE_YAML_FILES', raising=False)
    maybe_write_golden(sta_file, transactions)
    assert not _golden_path(sta_file).exists()

    monkeypatch.setenv('WRITE_YAML_FILES', '1')
    maybe_write_golden(sta_file, transactions)
    assert _golden_path(sta_file).exists()


def test_maybe_write_golden_keeps_a_mode_only_when_it_differs(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A lowercase debit mark only changes the output with the fixes on.
    sta_file = str(tmp_path / 'statement.sta')
    _ = pathlib.Path(sta_file).write_text(
        _STATEMENT.replace('C10,00', 'd10,00'), encoding='utf-8'
    )
    monkeypatch.setenv('WRITE_YAML_FILES', '1')

    maybe_write_golden(sta_file, mt940.parse(sta_file), 'default')
    maybe_write_golden(sta_file, mt940.parse(sta_file), 'all')
    assert not _golden_path(sta_file, 'all').exists()
    compare(get_yaml_data(sta_file, 'all'), mt940.parse(sta_file))

    fixed = mt940.parse(sta_file, options=MODES['all'])
    maybe_write_golden(sta_file, fixed, 'all')
    assert _golden_path(sta_file, 'all').exists()
    compare(get_yaml_data(sta_file, 'all'), fixed)

    # Back to identical output: the stale mode golden is removed again.
    maybe_write_golden(sta_file, mt940.parse(sta_file), 'all')
    assert not _golden_path(sta_file, 'all').exists()


@pytest.mark.parametrize('mode', sorted(MODES))
@pytest.mark.parametrize('sta_file', get_sta_files())
def test_parse(sta_file: str, mode: str) -> None:
    transactions = mt940.parse(sta_file, options=MODES[mode])
    maybe_write_golden(sta_file, transactions, mode)
    expected = get_yaml_data(sta_file, mode)
    assert isinstance(expected, mt940.models.Transactions)

    # Every model has to render without raising.
    _ = repr(transactions)
    _ = str(transactions)
    for value in transactions.data.values():
        _ = str(value)
        _ = repr(value)
    for transaction in transactions:
        _ = repr(transaction)
        _ = str(transaction)
        for value in transaction.data.values():
            _ = str(value)
            _ = repr(value)

    # Statement-level data, then the transactions themselves.
    compare(expected, transactions)
    compare(expected[:], transactions[:])


@pytest.mark.parametrize('mode', sorted(MODES))
@pytest.mark.parametrize('sta_file', get_sta_files())
def test_json_dump(sta_file: str, mode: str) -> None:
    transactions = mt940.parse(sta_file, options=MODES[mode])
    decoded: object = json.loads(
        json.dumps(transactions, cls=mt940.JSONEncoder)
    )
    assert isinstance(decoded, dict)
