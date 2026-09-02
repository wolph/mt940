"""Regression tests for banks that exceed the SWIFT field-length caps.

- Issue #111 (GLS / Atruvia): customer_reference longer than 16 chars.
- Issue #117 (Wise): extra_details (supplementary details) over 34 chars.
"""

import mt940


def test_issue_111_long_customer_reference() -> None:
    # GLS / Atruvia sends a 35-char customer reference followed by the //
    # bank-reference delimiter. This is handled by the opt-in StatementGLS tag
    # (relaxing the default would change Rabobank-style same-line parsing).
    gls = mt940.tags.StatementGLS()
    data = """:20:STARTUMS
:25:GENODEF1XXX/1234567890
:28C:0
:60F:C220706EUR100,00
:61:2207060706DR20,NTRFBIPI-dvT1FzfMqvzF5HaU4oetlH7SGRkonU//2022070616391534000
:86:116?00Ueberweisung
:62F:C220706EUR80,00
"""
    transaction = mt940.parse(data, tags={gls.id: gls})[0]
    assert (
        transaction.data['customer_reference']
        == 'BIPI-dvT1FzfMqvzF5HaU4oetlH7SGRkonU'
    )
    assert transaction.data['bank_reference'] == '2022070616391534000'
    assert str(transaction.data['amount']) == '-20 EUR'


def test_same_line_details_with_double_slash_preserved() -> None:
    # A // inside same-line details (e.g. a URL) must NOT be treated as the
    # bank-reference delimiter by the default Statement tag (backwards-compat
    # guard: the GLS support is opt-in for exactly this reason).
    data = """:20:STARTUMS
:25:NL12RABO0123456789
:28C:0
:60F:C220706EUR100,00
:61:2207060706C10,00N654NONREF          HTTP://SHOP EXAMPLE
:86:116?00Payment
:62F:C220706EUR110,00
"""
    transaction = mt940.parse(data)[0]
    assert transaction.data['customer_reference'] == 'NONREF          '
    assert transaction.data['extra_details'] == 'HTTP://SHOP EXAMPLE'
    assert transaction.data.get('bank_reference') is None


def test_issue_117_long_extra_details() -> None:
    # Wise sends supplementary details longer than the 34-char SWIFT cap.
    long_details = 'Sent money to John Doe for invoice 12345 reference ABCDE'
    assert len(long_details) > 34
    data = f""":20:STARTUMS
:25:WISE/1234567890
:28C:0
:60F:C220706EUR100,00
:61:2207060706C50,00NTRFsomeref//bankref123
{long_details}
:86:116?00Payment
:62F:C220706EUR150,00
"""
    transaction = mt940.parse(data)[0]
    assert transaction.data['extra_details'] == long_details
    assert str(transaction.data['amount']) == '50.00 EUR'


def test_rabobank_same_line_extra_details_unchanged() -> None:
    # Rabobank packs a 16-char (space-padded) customer reference plus extra
    # text on the same line, with no // delimiter. The relaxation must keep
    # splitting these (backwards compatibility).
    data = """:20:STARTUMS
:25:NL12RABO0123456789
:28C:0
:60F:C220706EUR100,00
:61:2207060706C10,00N654NONREF          TOMTE TUMMETOT AMERSFOORT
:86:116?00Payment
:62F:C220706EUR110,00
"""
    transaction = mt940.parse(data)[0]
    assert transaction.data['customer_reference'] == 'NONREF          '
    assert transaction.data['extra_details'] == 'TOMTE TUMMETOT AMERSFOORT'
