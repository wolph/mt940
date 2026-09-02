"""Issue #132: ``?31`` is the counterparty account, not part of the name.

5.0.0 mapped ``?31`` onto ``applicant_name``, so the account number was
welded to the front of the name and ``applicant_iban`` disappeared. That
stays the default. ``Options(applicant_iban=True)`` restores the 4.30.0
mapping.
"""

import pathlib

import mt940

FIXTURES = pathlib.Path(__file__).resolve().parent.parent
SEPA_SNIPPET = FIXTURES / 'betterplace' / 'sepa_snippet.sta'
FIXED = mt940.Options(applicant_iban=True)


def test_applicant_iban_is_opt_in() -> None:
    legacy = mt940.parse(SEPA_SNIPPET)[0].data
    assert 'applicant_iban' not in legacy
    assert (
        legacy['applicant_name']
        == 'DE14508800500194785000KARL        KAUFMANN'
    )

    fixed = mt940.parse(SEPA_SNIPPET, options=FIXED)[0].data
    assert fixed['applicant_iban'] == 'DE14508800500194785000'
    assert fixed['applicant_name'] == 'KARL        KAUFMANN'


def test_plain_account_numbers_land_in_the_same_field() -> None:
    # Not every bank puts an IBAN in ?31, cmxl statements carry plain account
    # numbers there. The 4.x field name is kept for compatibility.
    data = """:20:REF
:25:123456789
:28C:0
:60F:C200101EUR100,00
:61:2001010101C10,00NTRFNONREF
:86:051?00UEBERWEISUNG?20PURPOSE?30BANK?31234567?32SOME?33 NAME
:62F:C200101EUR110,00
"""
    legacy = mt940.parse(data)[0].data
    assert legacy['applicant_bin'] == 'BANK'
    assert 'applicant_iban' not in legacy
    assert legacy['applicant_name'] == '234567SOME NAME'

    fixed = mt940.parse(data, options=FIXED)[0].data
    assert fixed['applicant_bin'] == 'BANK'
    assert fixed['applicant_iban'] == '234567'
    assert fixed['applicant_name'] == 'SOME NAME'
