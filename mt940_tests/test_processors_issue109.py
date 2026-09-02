"""Issue #109: strip a dangling ' BIC' or ' IBAN' label from a detail segment.

A label with no value after it carries no information. These tests drive the
real segment pipeline (`_parse_segments` -> `_process_segments`) instead of
fabricating segment dictionaries, so the input matches what banks actually
send (segment keys are always two characters).
"""

# pyright: reportPrivateUsage=false
# The private segment helpers are the unit under test here.

import mt940


def _purpose(detail_str: str) -> list[str]:
    processors = mt940.processors
    segments = processors._parse_segments(detail_str)
    return processors._process_segments(segments)[processors.DETAIL_KEYS['20']]


def test_dangling_bic_is_stripped() -> None:
    # ?29 ends with a bare ' BIC' label and no BIC value (issue #109).
    purpose = _purpose('?20Purpose?29 DE69280123450012345670 BIC')
    assert purpose == ['Purpose', ' DE69280123450012345670']


def test_dangling_iban_is_stripped() -> None:
    # The same pattern with a bare ' IBAN' label must also be stripped.
    purpose = _purpose('?20Purpose?29 DE69280123450012345670 IBAN')
    assert purpose == ['Purpose', ' DE69280123450012345670']


def test_value_not_ending_in_label_is_unchanged() -> None:
    purpose = _purpose('?20Legit purpose text?29trailing content')
    assert purpose == ['Legit purpose text', 'trailing content']


def test_issue_109_end_to_end() -> None:
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


def test_parse_segments_without_a_delimiter_is_empty() -> None:
    # No '?' means no segment type ever starts, so nothing is captured.
    assert mt940.processors._parse_segments('plain text') == {}


def test_parse_segments_ignores_a_truncated_trailing_delimiter() -> None:
    # A '?' with fewer than two characters after it cannot open a segment.
    # The empty key holds the (empty) text before the first delimiter.
    assert mt940.processors._parse_segments('?20Purpose?2') == {
        '': '',
        '20': 'Purpose',
    }
    assert mt940.processors._parse_segments('?2') == {}
