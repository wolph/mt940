"""Read transactions and reconcile opening and closing balances."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import mt940

SOURCE: Path = Path(__file__).parent / 'fixtures' / 'statement.sta'


def main() -> None:
    """Print signed amounts and reconcile the supplied balances.

    Raises:
        TypeError: A required balance has no amount.
    """
    statement: mt940.models.Transactions = mt940.parse(SOURCE)
    opening: mt940.models.Balance = statement.data['final_opening_balance']
    closing: mt940.models.Balance = statement.data['final_closing_balance']
    print('Opening:', opening)
    total: Decimal = Decimal(0)
    transaction: mt940.models.Transaction
    for transaction in statement:
        amount: mt940.models.Amount = transaction.data['amount']
        total += amount.amount
        print(transaction.data['date'], amount)
    print('Movement:', total)
    print('Closing:', closing)
    if not isinstance(opening.amount, mt940.models.Amount):
        message: str = 'The example requires an opening amount'
        raise TypeError(message)
    if not isinstance(closing.amount, mt940.models.Amount):
        message = 'The example requires a closing amount'
        raise TypeError(message)
    reconciled: bool = opening.amount.amount + total == closing.amount.amount
    print('Reconciled:', reconciled)


if __name__ == '__main__':
    main()
