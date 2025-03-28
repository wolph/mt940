import unittest

import mt940


class TestPurposeFieldFormatting(unittest.TestCase):
    """Test for purpose field formatting in MT940 statements."""

    def test_purpose_field_formatting(self):
        """Test that the purpose field is correctly formatted."""
        # Parse the example from the issue #109
        trans = mt940.parse("""\
:61:2401231020DR30,00NDDTKREF+
:86:105?00Basislastschrift?10931?20EREF+DD-1-23.01.2024
?21KREF+20241022098765432109 00?22000000000237?23MREF+27
?24CRED+DE47ZZZ00012345678?25SVWZ+Mitgliedsbeitrag
?26Mein Verein EREF: D?27D-1-23.01.2024 MREF: 27 CRE
?28D: DE47ZZZ00012345678 IBAN:?29 DE69280123450012345670 BIC
?30GENODEF1WDH?31DE69280123450012345670
?32Mein Verein e.V.?34992?60: GENODEF1WDH
""")

        # Get the purpose field
        purpose = trans[0].data.get('purpose', '')

        # Check that the purpose field doesn't end with "BIC"
        self.assertFalse(purpose.endswith(' BIC'))

        # Check that the purpose field contains the IBAN
        self.assertTrue('DE69280123450012345670' in purpose)


if __name__ == '__main__':
    unittest.main()
