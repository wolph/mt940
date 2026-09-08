"""Compare merged parsing with separate statement collections."""

from __future__ import annotations

from pathlib import Path

import mt940

SOURCE: Path = Path(__file__).parent / 'fixtures' / 'statements.sta'


def main() -> None:
    """Print separate metadata and the merged collection's reference."""
    statements: list[mt940.models.Transactions] = mt940.parse_statements(
        SOURCE
    )
    statement: mt940.models.Transactions
    for statement in statements:
        print(statement.data['transaction_reference'], len(statement))
        print('Opening:', statement.data['final_opening_balance'])
        print('Closing:', statement.data['final_closing_balance'])
    merged: mt940.models.Transactions = mt940.parse(SOURCE)
    print('Merged:', len(merged), merged.data['transaction_reference'])


if __name__ == '__main__':
    main()
