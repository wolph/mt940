"""Export the synthetic statement with decimal strings."""

from __future__ import annotations

import json

import mt940

from examples.basic import SOURCE


def main() -> None:
    """Print complete statement metadata and transactions as JSON."""
    statement: mt940.models.Transactions = mt940.parse(SOURCE)
    print(
        json.dumps(statement, cls=mt940.JSONEncoder, indent=2, sort_keys=True)
    )


if __name__ == '__main__':
    main()
