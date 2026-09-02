"""Issue #109 as reported: the purpose field must not end in a bare label."""

import mt940

STATEMENT = """\
:61:2401231020DR30,00NDDTKREF+
:86:105?00Basislastschrift?10931?20EREF+DD-1-23.01.2024
?21KREF+20241022098765432109 00?22000000000237?23MREF+27
?24CRED+DE47ZZZ00012345678?25SVWZ+Mitgliedsbeitrag
?26Mein Verein EREF: D?27D-1-23.01.2024 MREF: 27 CRE
?28D: DE47ZZZ00012345678 IBAN:?29 DE69280123450012345670 BIC
?30GENODEF1WDH?31DE69280123450012345670
?32Mein Verein e.V.?34992?60: GENODEF1WDH
"""


def test_purpose_field_formatting() -> None:
    purpose: str = mt940.parse(STATEMENT)[0].data.get('purpose', '')

    # The dangling ' BIC' label is stripped, the IBAN before it is kept.
    assert not purpose.endswith(' BIC')
    assert 'DE69280123450012345670' in purpose
