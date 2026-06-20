"""Issue #109: strip a dangling ' BIC'/' IBAN' label (a label with no value)
from the end of a transaction-detail segment.

These tests drive the real segment pipeline (`_parse_segments` ->
`_process_segments`) instead of fabricating segment dictionaries, so the input
matches what banks actually send (segment keys are always two characters).
"""

import mt940


def _purpose(detail_str: str) -> list[str]:
    processors = mt940.processors
    segments = processors._parse_segments(detail_str)
    return processors._process_segments(segments)[processors.DETAIL_KEYS['20']]


def test_dangling_bic_is_stripped():
    # ?29 ends with a bare ' BIC' label and no BIC value (issue #109).
    purpose = _purpose('?20Purpose?29 DE69280123450012345670 BIC')
    assert purpose == ['Purpose', ' DE69280123450012345670']


def test_dangling_iban_is_stripped():
    # The same pattern with a bare ' IBAN' label must also be stripped.
    purpose = _purpose('?20Purpose?29 DE69280123450012345670 IBAN')
    assert purpose == ['Purpose', ' DE69280123450012345670']


def test_value_not_ending_in_label_is_unchanged():
    purpose = _purpose('?20Legit purpose text?29trailing content')
    assert purpose == ['Legit purpose text', 'trailing content']


def test_issue_109_end_to_end():
    data = """:20:STARTUMS
:25:GENODEF1XXX/1234567890
:28C:0
:60F:C240123EUR100,00
:61:2401231020DR30,00NDDTKREF+
:86:105?00Basislastschrift?20EREF+DD-1?29 DE69280123450012345670 BIC
:62F:C240123EUR70,00
"""
    transaction = mt940.parse(data)[0]
    # The dangling ' BIC' must not appear anywhere in the parsed details,
    # while the actual reference value is preserved.
    blob = ' '.join(str(v) for v in transaction.data.values())
    assert ' BIC' not in blob
    assert 'DE69280123450012345670' in blob
