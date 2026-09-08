"""Compare legacy and opt-in interpretation of a reversal-of-credit mark."""

from __future__ import annotations

import mt940

SOURCE: str = """:20:REVERSAL
:60F:C260101EUR100,00
:61:260102RC12,50NTRFREVERSAL
:62F:C260102EUR87,50
"""


def main() -> None:
    """Print the amount under disabled, selected and all enabled switches."""
    legacy: mt940.models.Transactions = mt940.parse(SOURCE)
    selected: mt940.models.Transactions = mt940.parse(
        SOURCE, options=mt940.Options(reversal_sign=True)
    )
    enabled: mt940.models.Transactions = mt940.parse(
        SOURCE, options=mt940.Options.all()
    )
    print('Default:', legacy[0].data['amount'])
    print('reversal_sign=True:', selected[0].data['amount'])
    print('Options.all():', enabled[0].data['amount'])
    print('Available switches:', len(mt940.Options.names()))


if __name__ == '__main__':
    main()
