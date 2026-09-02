"""Issue #105: first intermediate_opening_balance / account_identification.

With the default ``parse()`` every statement-scope tag merges into one dict,
so in files with several pages only the LAST ``:60M:`` / ``:25:`` survive.
``parse_statements()`` preserves per-``:20:``-block data (shape 1). This test
also covers the paged single-block shape (shape 2).
"""

import mt940
import pytest

TWO_BLOCKS = """:20:REF1
:25:ACC1
:28C:1/1
:60M:C231229EUR100,00
:61:2312290101C10,00NTRFREF//BANK
:62M:C231229EUR110,00
-
:20:REF2
:25:ACC2
:28C:1/2
:60M:C231230EUR110,00
:61:2312300101C5,00NTRFREF//BANK
:62M:C231230EUR115,00
-
"""

PAGED_SINGLE_BLOCK = """:20:REF1
:25:ACC1
:28C:1/1
:60M:C231229EUR100,00
:61:2312290101C10,00NTRFREF//BANK
:62M:C231229EUR110,00
:28C:1/2
:60M:C231230EUR110,00
:61:2312300101C5,00NTRFREF//BANK
:62M:C231230EUR115,00
-
"""


def test_two_blocks_first_intermediate_balance_preserved() -> None:
    statements = mt940.parse_statements(TWO_BLOCKS)
    assert len(statements) == 2
    assert str(statements[0].data['intermediate_opening_balance']).startswith(
        '100.00'
    )
    assert statements[0].data['account_identification'] == 'ACC1'
    assert statements[1].data['account_identification'] == 'ACC2'


@pytest.mark.xfail(
    strict=True, reason='issue #105 shape 2 -- pending decision'
)
def test_paged_single_block_first_intermediate_balance_accessible() -> None:
    statements = mt940.parse_statements(PAGED_SINGLE_BLOCK)
    first = statements[0].data['intermediate_opening_balance']
    assert str(first).startswith('100.00')
