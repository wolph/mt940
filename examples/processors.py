"""Extend a processor slot with a new list and replacement results."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import mt940

from examples.basic import SOURCE

if TYPE_CHECKING:
    from collections.abc import Callable


def add_category(
    transactions: mt940.models.Transactions,
    tag: mt940.tags.Tag,
    tag_dict: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    """Return a new result mapping with a category for this demo's details.

    Args:
        transactions: Collection currently being parsed.
        tag: Details tag selected by the parser.
        tag_dict: Captures passed into the tag.
        result: Result of the preceding details processor.

    Returns:
        A new mapping retaining every existing result field.
    """
    del transactions, tag, tag_dict
    details: str = result.get('transaction_details', '')
    category: str = 'supplies' if 'Coffee' in details else 'refund'
    return {**result, 'category': category}


def main() -> None:
    """Print categories after running the default and additional processors."""
    slot: str = 'post_transaction_details'
    callbacks: list[Callable[..., dict[str, Any]]] = [
        *mt940.models.Transactions.DEFAULT_PROCESSORS[slot],
        add_category,
    ]
    statement: mt940.models.Transactions = mt940.parse(
        SOURCE, processors={slot: callbacks}
    )
    transaction: mt940.models.Transaction
    for transaction in statement:
        print(
            transaction.data['transaction_details'],
            transaction.data['category'],
        )
    defaults: int = len(mt940.models.Transactions.DEFAULT_PROCESSORS[slot])
    print('Default callbacks:', defaults)


if __name__ == '__main__':
    main()
