"""Issue #132: ``?31`` is the counterparty account, not part of the name.

5.0.0 mapped ``?31`` onto ``applicant_name``, so the account number was
welded to the front of the name and ``applicant_iban`` disappeared. The
mapping from 4.30.0 is restored.
"""

import pathlib

import mt940

FIXTURES = pathlib.Path(__file__).resolve().parent.parent
SEPA_SNIPPET = FIXTURES / 'betterplace' / 'sepa_snippet.sta'


def test_applicant_iban_has_its_own_field() -> None:
    transaction = mt940.parse(SEPA_SNIPPET)[0].data
    assert transaction['applicant_iban'] == 'DE14508800500194785000'
    assert transaction['applicant_name'] == 'KARL        KAUFMANN'


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
    transaction = mt940.parse(data)[0].data
    assert transaction['applicant_bin'] == 'BANK'
    assert transaction['applicant_iban'] == '234567'
    assert transaction['applicant_name'] == 'SOME NAME'
