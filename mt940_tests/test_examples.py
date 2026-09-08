"""Execute the documentation examples and verify their recorded results."""

from __future__ import annotations

import json
import subprocess  # noqa: S404 (execute owned examples without a shell)
import sys
from decimal import Decimal
from pathlib import Path

import mt940
import pytest
from examples import compatibility, custom_tags, processors, statements
from examples.walkthrough import build_report

ROOT: Path = Path(__file__).resolve().parents[1]
EXAMPLES: Path = ROOT / 'examples'
MODULES: tuple[str, ...] = (
    'basic',
    'statements',
    'json_export',
    'custom_tags',
    'processors',
    'compatibility',
    'walkthrough',
)


@pytest.mark.parametrize('name', MODULES)
def test_recorded_example(name: str) -> None:
    assert (EXAMPLES / f'{name}.py').is_file()
    completed: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
        [sys.executable, '-m', f'examples.{name}'],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert not completed.stderr
    recorded: str = (EXAMPLES / 'output' / f'{name}.txt').read_text()
    assert completed.stdout == recorded


def test_synthetic_statement_balances() -> None:
    assert (EXAMPLES / 'fixtures' / 'statement.sta').is_file()
    statement: mt940.models.Transactions = mt940.parse(
        EXAMPLES / 'fixtures' / 'statement.sta'
    )
    assert len(statement) == 2
    assert statement[0].data['amount'].amount == Decimal('-12.50')
    assert statement[1].data['amount'].amount == Decimal('25.00')
    assert (
        statement.data['final_opening_balance'].amount.amount
        + sum((item.data['amount'].amount for item in statement), Decimal(0))
        == statement.data['final_closing_balance'].amount.amount
    )


def test_json_output_preserves_decimal_strings() -> None:
    assert (EXAMPLES / 'output' / 'json_export.txt').is_file()
    payload: dict[str, object] = json.loads(
        (EXAMPLES / 'output' / 'json_export.txt').read_text()
    )
    assert payload['account_identification'] == 'EXAMPLE-ACCOUNT'
    assert payload['final_closing_balance'] == {
        'amount': {'amount': '112.50', 'currency': 'EUR'},
        'date': '2026-01-02',
        'status': 'C',
    }


def test_custom_tag_stays_at_statement_scope() -> None:
    tag: custom_tags.Department = custom_tags.Department()
    result: mt940.models.Transactions = mt940.parse(
        ':20:EXAMPLE\n:61:260102C1,00NTRFREF\n:99:OPS',
        tags={tag.id: tag},
    )
    assert result.data['department'] == 'OPS'
    assert 'department' not in result[0].data
    assert tag.id not in mt940.tags.TAG_BY_ID


def test_processor_returns_new_fields_without_mutating_input() -> None:
    original: dict[str, str] = {'transaction_details': 'Coffee supplies'}
    result: dict[str, object] = processors.add_category(
        mt940.models.Transactions(),
        mt940.tags.TransactionDetails(),
        {},
        original,
    )
    assert result == {**original, 'category': 'supplies'}
    assert result is not original
    assert 'category' not in original
    assert (
        len(
            mt940.models.Transactions.DEFAULT_PROCESSORS[
                'post_transaction_details'
            ]
        )
        == 1
    )


def test_statement_example_preserves_separate_balances() -> None:
    separate: list[mt940.models.Transactions] = mt940.parse_statements(
        statements.SOURCE
    )
    assert len(separate) == 2
    assert separate[0].data['final_opening_balance'].amount.amount == Decimal(
        '100.00'
    )
    assert separate[1].data['final_opening_balance'].amount.amount == Decimal(
        '87.50'
    )
    merged: mt940.models.Transactions = mt940.parse(statements.SOURCE)
    assert len(merged) == 2
    assert merged.data['transaction_reference'] == 'EXAMPLE-002'


def test_compatibility_example_changes_only_requested_sign() -> None:
    legacy: mt940.models.Transactions = mt940.parse(compatibility.SOURCE)
    selected: mt940.models.Transactions = mt940.parse(
        compatibility.SOURCE, options=mt940.Options(reversal_sign=True)
    )
    assert legacy[0].data['amount'].amount == Decimal('12.50')
    assert selected[0].data['amount'].amount == Decimal('-12.50')
    assert selected[0].data['status'] == legacy[0].data['status'] == 'RC'
    assert not selected.options.strip_bom


def test_walkthrough_reports_reconciled_decimal_strings() -> None:
    report: dict[str, object] = build_report()
    assert report == {
        'account': 'EXAMPLE-ACCOUNT',
        'currency': 'EUR',
        'reconciled': True,
        'transactions': [
            {
                'date': '2026-01-02',
                'amount': '-12.50',
                'description': 'Coffee supplies',
            },
            {
                'date': '2026-01-02',
                'amount': '25.00',
                'description': 'Supplier refund',
            },
        ],
    }


def test_readme_primary_python_example() -> None:
    readme: str = (ROOT / 'README.md').read_text()
    example: str = readme.split('```python\n', 1)[1]
    code: str
    following: str
    code, following = example.split('```', 1)
    displayed: str = following.split('```text\n', 1)[1].split('```', 1)[0]
    completed: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
        [sys.executable, '-c', code],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert not completed.stderr
    assert completed.stdout == displayed
    expected: str = '2026-01-02 -12.50 EUR\n87.50 EUR @ 2026-01-02\n'
    assert completed.stdout == expected
