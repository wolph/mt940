"""Register a private statement tag without changing the built-in registry."""

from __future__ import annotations

from typing import ClassVar

import mt940


class Department(mt940.tags.Tag):
    """Read a fictional :99: department code into statement metadata."""

    id: ClassVar[int | str] = 99
    scope: ClassVar[
        type[mt940.models.Transactions | mt940.models.Transaction]
    ] = mt940.models.Transactions
    pattern: ClassVar[str] = r'^(?P<department>[A-Z]{2,8})$'


def main() -> None:
    """Print the custom tag's slug and captured department."""
    tag: Department = Department()
    statement: mt940.models.Transactions = mt940.parse(
        ':20:EXAMPLE\n:99:OPS', tags={tag.id: tag}
    )
    print('Slug:', tag.slug)
    print('Department:', statement.data['department'])
    print('Built-in registry changed:', tag.id in mt940.tags.TAG_BY_ID)


if __name__ == '__main__':
    main()
