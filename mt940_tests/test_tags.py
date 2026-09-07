import datetime
import pathlib
from typing import ClassVar

import mt940
import pytest

_tests_path = pathlib.Path(__file__).parent

# Minimal valid MT940 statement to wrap single-tag test values in.
_PREAMBLE = ':20:REF\n:25:ACC\n:28C:1\n'
_OPENING = ':60F:C231229EUR0,00\n'
_HEADER = _PREAMBLE + _OPENING
_FOOTER = ':62F:C231229EUR10,00\n'


_ALL = mt940.Options.all()


@pytest.mark.parametrize(
    ('options', 'expected_offset', 'expected_name'),
    [
        # 5.0.0 handed the HHMM digits to FixedOffset as a minute count.
        (mt940.Options(), datetime.timedelta(minutes=130), '0130'),
        # The subfield is HHMM (like ISO 8601 +0130): one hour and thirty
        # minutes east of UTC.
        (
            mt940.Options(timezone_offset=True),
            datetime.timedelta(hours=1, minutes=30),
            '90',
        ),
    ],
)
def test_date_time_indication_positive_offset(
    options: mt940.Options,
    expected_offset: datetime.timedelta,
    expected_name: str,
) -> None:
    transactions = mt940.parse(
        ':13D:1701191815+0130\n' + _HEADER + _FOOTER, options=options
    )
    date = transactions.data['date']
    assert date.utcoffset() == expected_offset
    assert date.tzname() == expected_name


@pytest.mark.parametrize(
    ('options', 'expected_offset', 'expected_name'),
    [
        # 5.0.0 could not parse a negative offset at all, so the default
        # applies its minute-count reading of the digits to the sign too.
        (mt940.Options(), -datetime.timedelta(minutes=500), '-0500'),
        # 1!x sign can be '-' as well (e.g. US banks): -0500 is UTC-5.
        (
            mt940.Options(timezone_offset=True),
            -datetime.timedelta(hours=5),
            '-300',
        ),
    ],
)
def test_date_time_indication_negative_offset(
    options: mt940.Options,
    expected_offset: datetime.timedelta,
    expected_name: str,
) -> None:
    transactions = mt940.parse(
        ':13D:1701191815-0500\n' + _HEADER + _FOOTER, options=options
    )
    date = transactions.data['date']
    assert date.utcoffset() == expected_offset
    assert date.tzname() == expected_name


_DETAIL_LINES = [f'line {i:02d} ' + 'x' * 57 for i in range(12)]


@pytest.mark.parametrize(
    ('options', 'expected'),
    [
        # 5.0.0 captured nine chunks of 65 characters and silently dropped
        # the rest, e.g. German banks packing many ?NN subfields.
        (mt940.Options(), '\n'.join(_DETAIL_LINES[:9])),
        (mt940.Options(unbounded_details=True), '\n'.join(_DETAIL_LINES)),
    ],
)
def test_transaction_details_long_multiline(
    options: mt940.Options, expected: str
) -> None:
    details = '\n'.join(_DETAIL_LINES)
    transactions = mt940.parse(
        _HEADER
        + ':61:2312290101D10,50NMSC\n'
        + ':86:'
        + details
        + '\n'
        + _FOOTER,
        options=options,
    )
    assert transactions[0].data['transaction_details'] == expected


@pytest.mark.parametrize(
    ('options', 'expected_length'),
    [
        (mt940.Options(), 585),
        (mt940.Options(unbounded_details=True), 700),
    ],
)
def test_transaction_details_single_long_line(
    options: mt940.Options, expected_length: int
) -> None:
    tag = mt940.tags.TransactionDetails()
    transactions = mt940.models.Transactions(options=options)
    parsed = tag.parse(transactions, 'x' * 700)
    assert len(parsed['transaction_details'] or '') == expected_length


class _WideDetails(mt940.tags.TransactionDetails):
    """The 4.x and 5.0.0 way past the cap: a subclass with its own pattern."""

    pattern: ClassVar[str] = r'(?P<transaction_details>[\s\S]*)'


class _PlainSubclass(mt940.tags.TransactionDetails):
    """A subclass that keeps the base pattern, so it keeps the cap too."""


@pytest.mark.parametrize(
    ('tag', 'expected_length'),
    [
        (_WideDetails(), 700),
        (_PlainSubclass(), 585),
    ],
    ids=['own_pattern', 'base_pattern'],
)
def test_transaction_details_subclass_pattern_is_honoured(
    tag: mt940.tags.TransactionDetails, expected_length: int
) -> None:
    # 5.1.0 cut a subclass's capture back to 585 characters, which broke the
    # workaround every 4.x and 5.0.0 user had for long details.
    transactions = mt940.models.Transactions()
    parsed = tag.parse(transactions, 'x' * 700)
    assert len(parsed['transaction_details'] or '') == expected_length


def test_transaction_details_subclass_pattern_through_parse() -> None:
    transactions = mt940.parse(
        _HEADER
        + ':61:2312291229C10,00NTRFNONREF//B\n:86:'
        + 'x' * 700
        + '\n'
        + _FOOTER,
        tags={86: _WideDetails()},
    )
    assert len(transactions[0].data['transaction_details']) == 700


@pytest.mark.parametrize(
    ('options', 'expected'),
    [
        # 5.0.0 turned a line without a sub-tag into a paragraph break once
        # there was text, dropping the line's content.
        (mt940.Options(), 'a\n\nb'),
        (mt940.Options(non_swift_free_text=True), 'a\nfree\nb'),
    ],
)
def test_non_swift_free_text_between_sub_tags(
    options: mt940.Options, expected: str
) -> None:
    tag = mt940.tags.NonSwift()
    transactions = mt940.models.Transactions(options=options)
    result = tag(transactions, {'non_swift': '01a\nfree\n02b'})
    assert result['non_swift_01'] == 'a'
    assert result['non_swift_02'] == 'b'
    assert result['non_swift_text'] == expected


@pytest.mark.parametrize(
    ('options', 'expected'),
    [
        (mt940.Options(), 'hello\n'),
        (mt940.Options(non_swift_free_text=True), 'hello\nworld'),
    ],
)
def test_non_swift_multiline_free_text(
    options: mt940.Options, expected: str
) -> None:
    # NS content is bank specific ("could be anything"). Multi-line values
    # whose lines do not all start with a two-digit sub-tag used to fail the
    # NS pattern and abort the whole parse. They parse in both modes now,
    # the default keeps the 5.0.0 line handling.
    transactions = mt940.parse(
        _HEADER + ':NS:hello\nworld\n' + _FOOTER, options=options
    )
    assert transactions.data['non_swift'] == 'hello\nworld'
    assert transactions.data['non_swift_text'] == expected


@pytest.mark.parametrize(
    ('options', 'expected'),
    [
        (mt940.Options(), 'foo\n'),
        (mt940.Options(non_swift_free_text=True), 'foo\nbar'),
    ],
)
def test_non_swift_structured_line_followed_by_free_text(
    options: mt940.Options, expected: str
) -> None:
    transactions = mt940.parse(
        _HEADER + ':NS:22foo\nbar\n' + _FOOTER, options=options
    )
    assert transactions.data['non_swift'] == '22foo\nbar'
    assert transactions.data['non_swift_22'] == 'foo'
    assert transactions.data['non_swift_text'] == expected


@pytest.mark.parametrize('options', [mt940.Options(), _ALL])
def test_non_swift_blank_lines_collapse(options: mt940.Options) -> None:
    # Direct tag call: blank lines between content are kept as single
    # paragraph separators in non_swift_text (mt940.parse strips blank
    # lines before tags ever see them). Both modes agree.
    tag = mt940.tags.NonSwift()
    result = tag(
        mt940.models.Transactions(options=options),
        {'non_swift': '22foo\n\n\n22bar'},
    )
    assert result['non_swift_text'] == 'foo\n\nbar'


_FLOOR_LIMIT_ONLY = (
    _PREAMBLE
    + ':34F:EUR 500,00\n'
    + ':61:0910201020C500,00NTRFNONREF//B\n'
    + ':86:Example\n'
)


def test_floor_limit_space_indicator_default_keeps_the_space() -> None:
    # Fiducia / Volksbank Ortenau sends ':34F:EUR 999999999999,99' (commit
    # d36c51b relaxed the regex for it). 5.0.0 let the space through into
    # the key, and since neither d_ nor c_floor_limit exists it found no
    # statement currency for the transactions either.
    transactions = mt940.parse(_FLOOR_LIMIT_ONLY)
    assert str(transactions.data[' _floor_limit']) == '500.00 EUR'
    assert 'd_floor_limit' not in transactions.data
    assert transactions.currency is None
    assert transactions[0].data['amount'].currency is None


def test_floor_limit_space_indicator_treated_as_absent() -> None:
    # A blank D/C mark means "applies to both", like an absent mark, and the
    # floor limit then also supplies the statement currency.
    transactions = mt940.parse(
        _FLOOR_LIMIT_ONLY, options=mt940.Options(floor_limit_blank_mark=True)
    )
    assert ' _floor_limit' not in transactions.data
    assert str(transactions.data['d_floor_limit']) == '-500.00 EUR'
    assert str(transactions.data['c_floor_limit']) == '500.00 EUR'
    assert transactions.currency == 'EUR'
    assert transactions[0].data['amount'].currency == 'EUR'


@pytest.mark.parametrize(
    ('options', 'expected'),
    [
        # 5.0.0 lowercased the key but compared the mark with 'D' only, so
        # the debit limit came back positive.
        (mt940.Options(), '10.00 EUR'),
        (mt940.Options(case_insensitive_marks=True), '-10.00 EUR'),
    ],
)
def test_floor_limit_lowercase_indicator(
    options: mt940.Options, expected: str
) -> None:
    # The tag regexes are compiled with re.IGNORECASE, so a lowercase mark
    # parses. Whether it signs like its uppercase form is the option.
    transactions = mt940.parse(
        _PREAMBLE + ':34F:EURd10,00\n' + _OPENING + _FOOTER, options=options
    )
    assert str(transactions.data['d_floor_limit']) == expected


def test_floor_limit_without_a_mark_group_applies_to_both() -> None:
    # A custom pattern may leave the mark group out entirely. 5.0.0 treated
    # the resulting None like an absent mark.
    tag = mt940.tags.FloorLimitIndicator()
    result = tag(
        mt940.models.Transactions(),
        {'currency': 'EUR', 'status': None, 'amount': '5,00'},
    )
    assert str(result['d_floor_limit']) == '-5.00 EUR'
    assert str(result['c_floor_limit']) == '5.00 EUR'


class MultilineGroupTag(mt940.tags.Tag):
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


@pytest.mark.parametrize(
    ('options', 'expected'),
    [
        # 5.0.0 negated a plain D only, a reversed credit stayed positive.
        (mt940.Options(), '10.50 EUR'),
        (mt940.Options(reversal_sign=True), '-10.50 EUR'),
    ],
)
def test_statement_rc_reversal_amount(
    options: mt940.Options, expected: str
) -> None:
    transactions = mt940.parse(
        _HEADER + ':61:2312290101RC10,50NTRFREF//BANK\n' + _FOOTER,
        options=options,
    )
    data = transactions[0].data
    assert data['status'] == 'RC'
    assert str(data['amount']) == expected


@pytest.mark.parametrize(
    ('options', 'expected_rc'),
    [(mt940.Options(), '10.50 EUR'), (_ALL, '-10.50 EUR')],
)
def test_statement_reversal_marks_parse(
    options: mt940.Options, expected_rc: str
) -> None:
    # RC/RD marks (2a subfield) parse and are preserved in `status`. RD is
    # a reversed debit (money back in) and stays positive in both modes, RC
    # a reversed credit (money back out) and negative once opted in.
    transactions = mt940.parse(
        _HEADER
        + ':61:2312290101RD10,50NTRFREF//BANK\n'
        + ':61:2312290101RC10,50NTRFREF//BANK\n'
        + _FOOTER,
        options=options,
    )
    assert transactions[0].data['status'] == 'RD'
    assert str(transactions[0].data['amount']) == '10.50 EUR'
    assert transactions[1].data['status'] == 'RC'
    assert str(transactions[1].data['amount']) == expected_rc


def test_statement_amount_without_decimals() -> None:
    # 15d allows a trailing decimal comma with no fraction digits.
    transactions = mt940.parse(
        _HEADER + ':61:2312290101C10,NTRFREF//BANK\n' + _FOOTER
    )
    assert str(transactions[0].data['amount']) == '10 EUR'


@pytest.mark.parametrize(
    ('options', 'expected'),
    [
        # 5.0.0 compared the mark with 'D' only, so the debit was silently
        # stored as positive.
        (mt940.Options(), '10.50 EUR'),
        (mt940.Options(case_insensitive_marks=True), '-10.50 EUR'),
    ],
)
def test_statement_lowercase_debit_mark(
    options: mt940.Options, expected: str
) -> None:
    # The tag patterns are compiled with re.IGNORECASE, so a lowercase 'd'
    # debit mark is accepted and kept as parsed in `status`.
    transactions = mt940.parse(
        _HEADER + ':61:2312290101d10,50NTRFREF//BANK\n' + _FOOTER,
        options=options,
    )
    data = transactions[0].data
    assert data['status'] == 'd'
    assert str(data['amount']) == expected


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
    assert balance.date == mt940.models.Date(2024, 2, 29)


@pytest.mark.parametrize('options', [mt940.Options(), _ALL])
def test_date_time_indication_without_offset(options: mt940.Options) -> None:
    # The offset is optional in the pattern. A bare 10-digit :13: must not
    # crash and yields a naive datetime in both modes.
    transactions = mt940.parse(
        ':13:1701191815\n' + _HEADER + _FOOTER, options=options
    )
    date = transactions.data['date']
    assert date == mt940.models.DateTime(2017, 1, 19, 18, 15)
    assert date.tzinfo is None


@pytest.fixture
def long_statement_number() -> str:
    with (_tests_path / 'self-provided' / 'long_statement_number.sta').open(
        encoding='utf-8'
    ) as fh:
        return fh.read()


class MyStatementNumber(mt940.tags.Tag):
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
        (
            'ASNB/mt940.txt',
            mt940.models.Date(2020, 1, 1),
            mt940.models.Date(2020, 1, 31),
        ),
        ('ASNB/mt940_with_spaces_for_entry_date.txt', None, None),
    ],
)
def test_asnb_tags(
    path_to_file: str,
    first_expected_entry_date: mt940.models.Date | None,
    last_expected_entry_date: mt940.models.Date | None,
) -> None:
    with _tests_path.joinpath(path_to_file).open(encoding='utf-8') as fh:
        data = fh.read()
        tag_parser = mt940.tags.StatementASNB()
        trs = mt940.models.Transactions(tags={tag_parser.id: tag_parser})

        _ = trs.parse(data)

        assert trs.data == {
            'account_identification': 'NL81ASNB9999999999',
            'transaction_reference': '0000000000',
            'statement_number': '31',
            'sequence_number': '1',
            'final_opening_balance': mt940.models.Balance(
                status='C',
                amount=mt940.models.Amount('404.81', 'C', 'EUR'),
                date=mt940.models.Date(2020, 1, 31),
            ),
            'final_closing_balance': mt940.models.Balance(
                status='C',
                amount=mt940.models.Amount('501.23', 'C', 'EUR'),
                date=mt940.models.Date(2020, 1, 31),
            ),
        }
        assert len(trs) == 8
        # test first entry
        td = trs.transactions[0].data.pop('transaction_details')

        first_expected_transaction_data = {
            'status': 'D',
            'funds_code': None,
            'amount': mt940.models.Amount('65.00', 'D', 'EUR'),
            'id': 'NOVB',
            'customer_reference': 'NL47INGB9999999999',
            'bank_reference': None,
            'extra_details': 'hr gjlm paulissen',
            'currency': 'EUR',
            'date': mt940.models.Date(2020, 1, 1),
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
        assert trs.transactions[1].data['amount'] == mt940.models.Amount(
            '1000.00', 'C', 'EUR'
        )
        assert trs.transactions[2].data['amount'] == mt940.models.Amount(
            '801.55', 'D', 'EUR'
        )
        assert trs.transactions[3].data['amount'] == mt940.models.Amount(
            '1.65', 'D', 'EUR'
        )
        assert trs.transactions[4].data['amount'] == mt940.models.Amount(
            '828.72', 'C', 'EUR'
        )
        assert trs.transactions[5].data['amount'] == mt940.models.Amount(
            '1000.00', 'D', 'EUR'
        )
        assert trs.transactions[6].data['amount'] == mt940.models.Amount(
            '1000.18', 'C', 'EUR'
        )

        td = trs.transactions[7].data.pop('transaction_details')
        last_expected_transaction_data = {
            'status': 'D',
            'funds_code': None,
            'amount': mt940.models.Amount('903.76', 'D', 'EUR'),
            'id': 'NIDB',
            'customer_reference': 'NL08ABNA9999999999',
            'bank_reference': None,
            'extra_details': 'international card services',
            'currency': 'EUR',
            'date': mt940.models.Date(2020, 1, 31),
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


def test_tags_compare_by_identity() -> None:
    # 5.0.0 semantics: every instance is its own set member and dictionary
    # key, while the hash stays id-based so an object hashes like itself.
    first = mt940.tags.Statement()
    same = first
    second = mt940.tags.Statement()
    assert first == same
    assert first != second
    assert hash(first) == hash(second)
    assert len({first, second}) == 2
    assert first != mt940.tags.StatementASNB()
    assert first != first.id


def test_asnb_statement_keeps_its_call_override() -> None:
    # 5.0.0 defined the pass-through on the class itself, so it stays.
    assert '__call__' in vars(mt940.tags.StatementASNB)
