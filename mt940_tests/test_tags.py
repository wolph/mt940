import datetime
import pathlib
from typing import ClassVar

import mt940
import pytest
from mt940 import models, tags

_tests_path = pathlib.Path(__file__).parent

# Minimal valid MT940 statement to wrap single-tag test values in.
_PREAMBLE = ':20:REF\n:25:ACC\n:28C:1\n'
_OPENING = ':60F:C231229EUR0,00\n'
_HEADER = _PREAMBLE + _OPENING
_FOOTER = ':62F:C231229EUR10,00\n'


def test_date_time_indication_positive_offset_is_hhmm() -> None:
    # The :13(D): offset subfield is HHMM (like ISO 8601 +0130), not a
    # number of minutes: +0130 means 1 hour 30 minutes.
    transactions = mt940.parse(':13D:1701191815+0130\n' + _HEADER + _FOOTER)
    date = transactions.data['date']
    assert date.utcoffset() == datetime.timedelta(hours=1, minutes=30)


def test_date_time_indication_negative_offset() -> None:
    # 1!x sign can be '-' as well (e.g. US banks): -0500 is UTC-5.
    transactions = mt940.parse(':13D:1701191815-0500\n' + _HEADER + _FOOTER)
    date = transactions.data['date']
    assert date.utcoffset() == -datetime.timedelta(hours=5)


def test_transaction_details_long_multiline_not_truncated() -> None:
    # The old :86: pattern capped the capture at nine 65-char chunks
    # (~593 chars). Longer details, e.g. German banks packing many ?NN
    # subfields -- were silently truncated. The cap had already been bumped
    # once (commit 4575222) for exactly this reason.
    lines = [f'line {i:02d} ' + 'x' * 57 for i in range(12)]
    details = '\n'.join(lines)
    transactions = mt940.parse(
        _HEADER
        + ':61:2312290101D10,50NMSC\n'
        + ':86:'
        + details
        + '\n'
        + _FOOTER
    )
    assert transactions[0].data['transaction_details'] == details


def test_non_swift_multiline_free_text() -> None:
    # NS content is bank specific ("could be anything"). Multi-line values
    # whose lines do not all start with a two-digit sub-tag used to fail the
    # NS pattern and abort the whole parse.
    transactions = mt940.parse(_HEADER + ':NS:hello\nworld\n' + _FOOTER)
    assert transactions.data['non_swift'] == 'hello\nworld'
    assert transactions.data['non_swift_text'] == 'hello\nworld'


def test_non_swift_structured_line_followed_by_free_text() -> None:
    transactions = mt940.parse(_HEADER + ':NS:22foo\nbar\n' + _FOOTER)
    assert transactions.data['non_swift'] == '22foo\nbar'
    assert transactions.data['non_swift_22'] == 'foo'
    assert transactions.data['non_swift_text'] == 'foo\nbar'


def test_non_swift_blank_lines_collapse() -> None:
    # Direct tag call: blank lines between content are kept as single
    # paragraph separators in non_swift_text (mt940.parse strips blank
    # lines before tags ever see them).
    tag = tags.NonSwift()
    result = tag(
        mt940.models.Transactions(), {'non_swift': '22foo\n\n\n22bar'}
    )
    assert result['non_swift_text'] == 'foo\n\nbar'


def test_floor_limit_space_indicator_treated_as_absent() -> None:
    # Fiducia / Volksbank Ortenau sends ':34F:EUR 999999999999,99' (commit
    # d36c51b relaxed the regex for it). A blank D/C mark means "applies to
    # both", like an absent mark -- it must not create a ' _floor_limit' key.
    transactions = mt940.parse(
        _PREAMBLE + ':34F:EUR 999999999999,99\n' + _OPENING + _FOOTER
    )
    assert ' _floor_limit' not in transactions.data
    assert str(transactions.data['d_floor_limit']) == '-999999999999.99 EUR'
    assert str(transactions.data['c_floor_limit']) == '999999999999.99 EUR'


def test_floor_limit_lowercase_indicator_normalized() -> None:
    # The tag regexes are compiled with re.IGNORECASE, so a lowercase mark
    # must behave exactly like its uppercase form (debit -> negative).
    transactions = mt940.parse(
        _PREAMBLE + ':34F:EURd10,00\n' + _OPENING + _FOOTER
    )
    assert str(transactions.data['d_floor_limit']) == '-10.00 EUR'


class MultilineGroupTag(tags.Tag):
    """Tag whose (valid) pattern spreads one group over several lines."""

    id: ClassVar[str | int] = 28
    pattern: ClassVar[str] = r"""
    (?P<statement_number>
        \d+
    )
    $"""


def test_unparseable_value_raises_runtime_error() -> None:
    # Tag.parse documents RuntimeError for unparsable values, but the
    # debug helper re-compiles the pattern line by line. For patterns with
    # multi-line groups the unbalanced fragments raised re.error instead.
    tag_parser = MultilineGroupTag()
    transactions = mt940.models.Transactions(tags={tag_parser.id: tag_parser})
    with pytest.raises(RuntimeError, match='Unable to parse'):
        _ = transactions.parse(':20:REF\n:28C:NOTDIGITS\n')


def test_statement_rc_reversal_amount_is_negative() -> None:
    transactions = mt940.parse(
        _HEADER + ':61:2312290101RC10,50NTRFREF//BANK\n' + _FOOTER
    )
    data = transactions[0].data
    assert data['status'] == 'RC'
    assert str(data['amount']) == '-10.50 EUR'


def test_statement_reversal_marks_parse() -> None:
    # RC/RD marks (2a subfield) parse and are preserved in `status`. RD is
    # a reversed debit (money back in, positive), RC a reversed credit
    # (money back out, negative).
    transactions = mt940.parse(
        _HEADER
        + ':61:2312290101RD10,50NTRFREF//BANK\n'
        + ':61:2312290101RC10,50NTRFREF//BANK\n'
        + _FOOTER
    )
    assert transactions[0].data['status'] == 'RD'
    assert str(transactions[0].data['amount']) == '10.50 EUR'
    assert transactions[1].data['status'] == 'RC'
    assert str(transactions[1].data['amount']) == '-10.50 EUR'


def test_statement_amount_without_decimals() -> None:
    # 15d allows a trailing decimal comma with no fraction digits.
    transactions = mt940.parse(
        _HEADER + ':61:2312290101C10,NTRFREF//BANK\n' + _FOOTER
    )
    assert str(transactions[0].data['amount']) == '10 EUR'


def test_statement_lowercase_debit_mark_is_negative() -> None:
    # The tag patterns are compiled with re.IGNORECASE, so a lowercase 'd'
    # debit mark is accepted. Amount must still treat it as a debit and
    # negate the amount, otherwise a debit is silently stored as positive.
    transactions = mt940.parse(
        _HEADER + ':61:2312290101d10,50NTRFREF//BANK\n' + _FOOTER
    )
    data = transactions[0].data
    assert data['status'] == 'd'
    assert str(data['amount']) == '-10.50 EUR'


def test_statement_second_double_slash_stays_in_bank_reference() -> None:
    # Only the first // separates the bank reference. A second one is kept
    # as part of the reference content.
    transactions = mt940.parse(
        _HEADER + ':61:2312290101C10,50NTRFREF//BANK//EXTRA\n' + _FOOTER
    )
    data = transactions[0].data
    assert data['customer_reference'] == 'REF'
    assert data['bank_reference'] == 'BANK//EXTRA'


_LEAP_DAY_STATEMENT = """:20:REF
:25:ACC
:28C:1
:60F:C240229EUR0,00
:61:2402290229C10,50NTRFREF
:62F:C240229EUR10,50
"""


def test_balance_on_leap_day() -> None:
    transactions = mt940.parse(_LEAP_DAY_STATEMENT)
    balance = transactions.data['final_opening_balance']
    assert balance.date == models.Date(2024, 2, 29)


def test_date_time_indication_without_offset() -> None:
    # The offset is optional in the pattern. A bare 10-digit :13: must not
    # crash and yields a naive datetime.
    transactions = mt940.parse(':13:1701191815\n' + _HEADER + _FOOTER)
    date = transactions.data['date']
    assert date == models.DateTime(2017, 1, 19, 18, 15)
    assert date.tzinfo is None


@pytest.fixture
def long_statement_number() -> str:
    with (_tests_path / 'self-provided' / 'long_statement_number.sta').open(
        encoding='utf-8'
    ) as fh:
        return fh.read()


class MyStatementNumber(tags.Tag):
    """Statement number / sequence number.

    Pattern: 10n
    """

    id: ClassVar[str | int] = 28
    pattern: ClassVar[str] = r"""
    (?P<statement_number>\d{1,10})  # 10n
    $"""


def test_specify_different_tag_classes(long_statement_number: str) -> None:
    tag_parser = MyStatementNumber()
    transactions = mt940.models.Transactions(tags={tag_parser.id: tag_parser})
    _ = transactions.parse(long_statement_number)
    assert transactions.data.get('statement_number') == '1810118101'


@pytest.mark.parametrize(
    ('path_to_file', 'first_expected_entry_date', 'last_expected_entry_date'),
    [
        ('ASNB/mt940.txt', models.Date(2020, 1, 1), models.Date(2020, 1, 31)),
        ('ASNB/mt940_with_spaces_for_entry_date.txt', None, None),
    ],
)
def test_asnb_tags(
    path_to_file: str,
    first_expected_entry_date: models.Date | None,
    last_expected_entry_date: models.Date | None,
) -> None:
    with _tests_path.joinpath(path_to_file).open(encoding='utf-8') as fh:
        data = fh.read()
        tag_parser = tags.StatementASNB()
        trs = mt940.models.Transactions(tags={tag_parser.id: tag_parser})

        _ = trs.parse(data)

        assert trs.data == {
            'account_identification': 'NL81ASNB9999999999',
            'transaction_reference': '0000000000',
            'statement_number': '31',
            'sequence_number': '1',
            'final_opening_balance': models.Balance(
                status='C',
                amount=models.Amount('404.81', 'C', 'EUR'),
                date=models.Date(2020, 1, 31),
            ),
            'final_closing_balance': models.Balance(
                status='C',
                amount=models.Amount('501.23', 'C', 'EUR'),
                date=models.Date(2020, 1, 31),
            ),
        }
        assert len(trs) == 8
        # test first entry
        td = trs.transactions[0].data.pop('transaction_details')

        first_expected_transaction_data = {
            'status': 'D',
            'funds_code': None,
            'amount': models.Amount('65.00', 'D', 'EUR'),
            'id': 'NOVB',
            'customer_reference': 'NL47INGB9999999999',
            'bank_reference': None,
            'extra_details': 'hr gjlm paulissen',
            'currency': 'EUR',
            'date': models.Date(2020, 1, 1),
            'transaction_reference': '0000000000',
        }
        if first_expected_entry_date:
            first_expected_transaction_data['entry_date'] = (
                first_expected_entry_date
            )
            first_expected_transaction_data['guessed_entry_date'] = (
                first_expected_entry_date
            )

        assert trs.transactions[0].data == first_expected_transaction_data

        assert td == 'NL47INGB9999999999 hr gjlm paulissen\nBetaling sieraden'
        assert trs.transactions[1].data['amount'] == models.Amount(
            '1000.00', 'C', 'EUR'
        )
        assert trs.transactions[2].data['amount'] == models.Amount(
            '801.55', 'D', 'EUR'
        )
        assert trs.transactions[3].data['amount'] == models.Amount(
            '1.65', 'D', 'EUR'
        )
        assert trs.transactions[4].data['amount'] == models.Amount(
            '828.72', 'C', 'EUR'
        )
        assert trs.transactions[5].data['amount'] == models.Amount(
            '1000.00', 'D', 'EUR'
        )
        assert trs.transactions[6].data['amount'] == models.Amount(
            '1000.18', 'C', 'EUR'
        )

        td = trs.transactions[7].data.pop('transaction_details')
        last_expected_transaction_data = {
            'status': 'D',
            'funds_code': None,
            'amount': models.Amount('903.76', 'D', 'EUR'),
            'id': 'NIDB',
            'customer_reference': 'NL08ABNA9999999999',
            'bank_reference': None,
            'extra_details': 'international card services',
            'currency': 'EUR',
            'date': models.Date(2020, 1, 31),
            'transaction_reference': '0000000000',
        }
        if last_expected_entry_date:
            last_expected_transaction_data['entry_date'] = (
                last_expected_entry_date
            )
            last_expected_transaction_data['guessed_entry_date'] = (
                last_expected_entry_date
            )
        assert trs.transactions[7].data == last_expected_transaction_data
        assert td[0:46] == ('NL08ABNA9999999999 international card services')
        assert td[47:112] == (
            '000000000000000000000000000000000 0000000000000000 Betaling aan I'
        )
        assert td[113:176] == (
            'CS 99999999999 ICS Referentie: 2020-01-31 21:27 000000000000000'
        )


def test_unknown_tag_id_is_skipped() -> None:
    # :99: is syntactically a tag but has no parser, so the line is dropped
    # while the known tags around it still parse.
    transactions = mt940.parse(
        ':20:REF\n:25:ACC\n:99:IGNORED\n:28C:1\n' + _OPENING + _FOOTER
    )
    assert transactions.data['transaction_reference'] == 'REF'
    assert transactions.data['account_identification'] == 'ACC'
    assert transactions.data['statement_number'] == '1'
    assert 'IGNORED' not in str(transactions.data)
