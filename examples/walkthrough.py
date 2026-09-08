"""Validate a parsed statement, reconcile balances and export a report."""

from __future__ import annotations

import json
from decimal import Decimal

import mt940

from examples.basic import SOURCE


def build_report() -> dict[str, object]:
    """Build an application-owned JSON shape from a complete statement.

    Returns:
        Account, currency, balance check and selected transaction fields.

    Raises:
        TypeError: A required balance or transaction amount is unavailable.
        ValueError: A transaction uses a different currency from its balance.
    """
    source: bytes = SOURCE.read_bytes()
    statement: mt940.models.Transactions = mt940.parse(
        source, encoding='utf-8'
    )
    opening: object = statement.data.get('final_opening_balance')
    closing: object = statement.data.get('final_closing_balance')
    if not isinstance(opening, mt940.models.Balance) or not isinstance(
        closing, mt940.models.Balance
    ):
        message: str = 'Opening and closing balances are required'
        raise TypeError(message)
    if not isinstance(opening.amount, mt940.models.Amount) or not isinstance(
        closing.amount, mt940.models.Amount
    ):
        message = 'Both balances must contain amounts'
        raise TypeError(message)
    rows: list[dict[str, str]] = []
    movement: Decimal = Decimal(0)
    transaction: mt940.models.Transaction
    for transaction in statement:
        amount: object = transaction.data.get('amount')
        if not isinstance(amount, mt940.models.Amount):
            message = 'Every transaction must contain an amount'
            raise TypeError(message)
        if amount.currency != opening.amount.currency:
            message = 'Transaction and balance currencies must match'
            raise ValueError(message)
        movement += amount.amount
        rows.append({
            'date': str(transaction.data['date']),
            'amount': str(amount.amount),
            'description': str(
                transaction.data.get('transaction_details', '')
            ),
        })
    reconciled: bool = (
        opening.amount.amount + movement == closing.amount.amount
    )
    return {
        'account': statement.data['account_identification'],
        'currency': opening.amount.currency,
        'reconciled': reconciled,
        'transactions': rows,
    }


def main() -> None:
    """Print a report that uses only standard JSON types."""
    print(json.dumps(build_report(), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
