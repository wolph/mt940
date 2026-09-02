import json
import os
import pathlib
import typing

import mt940
import pytest

if typing.TYPE_CHECKING:
    from mt940.models import Transactions

_tests_path: pathlib.Path = pathlib.Path(__file__).parent


@pytest.fixture
def sta_data() -> str:
    """Provide data from abnamro.sta as a string.

    Returns:
        Contents of abnamro.sta.
    """
    with (_tests_path / 'jejik' / 'abnamro.sta').open() as fh:
        return fh.read()


@pytest.fixture
def february_30_data() -> str:
    """Provide data from february_30.sta as a string.

    Returns:
        Contents of february_30.sta (with invalid date).
    """
    with (_tests_path / 'self-provided' / 'february_30.sta').open() as fh:
        return fh.read()


def test_date_fixup_pre_processor(february_30_data: str) -> None:
    transactions = mt940.models.Transactions(
        processors={
            'pre_statement': [
                mt940.processors.date_fixup_pre_processor,
            ],
        }
    )
    transactions.parse(february_30_data)
    assert transactions[0].data['date'] == mt940.models.Date(2016, 2, 29)


def test_parse_data() -> None:
    with (_tests_path / 'jejik' / 'abnamro.sta').open() as fh:
        mt940.parse(fh.read())


def test_parse_fh() -> None:
    with (_tests_path / 'jejik' / 'abnamro.sta').open() as fh:
        mt940.parse(fh)


def test_parse_filename() -> None:
    path = 'mt940_tests/jejik/abnamro.sta'
    path = path.replace('/', os.pathsep)
    mt940.parse(path)


def test_pre_processor(sta_data: str) -> None:
    transactions = mt940.models.Transactions(
        processors={
            'pre_final_closing_balance': [
                mt940.processors.add_currency_pre_processor('USD'),
            ],
            'pre_final_opening_balance': [
                mt940.processors.add_currency_pre_processor('EUR'),
            ],
        }
    )
    transactions.parse(sta_data)
    assert transactions.data['final_closing_balance'].amount.currency == 'USD'
    assert transactions.data['final_opening_balance'].amount.currency == 'EUR'


def test_post_processor(sta_data: str) -> None:
    transactions = mt940.models.Transactions(
        processors={
            'post_closing_balance': [
                mt940.processors.date_cleanup_post_processor,
            ],
        }
    )
    transactions.parse(sta_data)
    assert 'closing_balance_day' not in transactions.data


@pytest.fixture
def mBank_mt942_data() -> str:
    """Provide data from mt942.sta as a string for mBank-specific tests.

    Returns:
        Contents of mt942.sta.
    """
    with (_tests_path / 'mBank' / 'mt942.sta').open() as fh:
        return fh.read()


def test_mBank_processors(mBank_mt942_data: str) -> None:
    transactions = mt940.models.Transactions(
        processors={
            'post_transaction_details': [
                mt940.processors.mBank_set_transaction_code,
                mt940.processors.mBank_set_iph_id,
                mt940.processors.mBank_set_tnr,
            ],
        }
    )
    transaction = transactions.parse(mBank_mt942_data)[0].data
    assert transaction['transaction_code'] == 911
    assert transaction['iph_id'] == '000000000001'
    assert transaction['tnr'] == '179171073864111.010001'


def test_transaction_details_post_processor_with_space() -> None:
    filename = _tests_path / 'betterplace' / 'sepa_mt9401.sta'
    transactions = mt940.parse(filename)
    transaction2 = transactions[0].data

    transactions = mt940.parse(
        filename,
        processors={
            'post_transaction_details': [
                mt940.processors.transaction_details_post_processor_with_space,
            ],
        },
    )
    transaction = transactions[0].data
    assert (
        transaction2['end_to_end_reference']
        != transaction['end_to_end_reference']
    )


@pytest.fixture
def mBank_with_newline_in_tnr() -> str:
    """Provide data from with_newline_in_tnr.sta for testing newline in TNR.

    Returns:
        Contents of with_newline_in_tnr.sta.
    """
    with (_tests_path / 'mBank' / 'with_newline_in_tnr.sta').open() as fh:
        return fh.read()


def test_mBank_set_tnr_parses_tnr_with_newlines(
    mBank_with_newline_in_tnr: str,
) -> None:
    transactions = mt940.models.Transactions(
        processors={
            'post_transaction_details': [
                mt940.processors.mBank_set_tnr,
            ],
        }
    )
    transactions_ = transactions.parse(mBank_with_newline_in_tnr)
    assert transactions_[0].data['tnr'] == '179301073837502.000001'
    assert transactions_[1].data['tnr'] == '179301073844398.000001'


def test_citi_bank_processors() -> None:
    with (_tests_path / 'citi' / 'mt940.txt').open() as fh:
        transactions: Transactions = mt940.parse(fh.read())
        data: dict[str, typing.Any] = transactions.data
        assert data['account_identification'] == '123456789'
        assert data['statement_number'] == '1'
        assert data['sequence_number'] == '1'
        assert str(data['final_opening_balance'].amount.amount) == '17376.67'
        assert data['final_opening_balance'].amount.currency == 'USD'
        assert str(data['final_closing_balance'].amount.amount) == '16233.92'
        assert data['final_closing_balance'].amount.currency == 'USD'
        assert len(transactions) == 5
        expected_date = mt940.models.Date(2024, 3, 12)
        assert transactions[0].data['date'] == expected_date


def test_json_round_trip_preserves_model_values() -> None:
    """`mt940.JSONEncoder` serialises every model type and round-trips.

    The existing ``test_json_dump`` only calls ``json.dumps`` over ``.sta``
    fixtures. This exercises the full ``dumps`` -> ``loads`` round-trip and
    asserts the string forms of the nested ``Balance``/``Amount``/``Date``
    value types, which were previously unchecked.
    """
    transactions = mt940.parse(str(_tests_path / 'jejik' / 'abnamro.sta'))
    decoded = json.loads(json.dumps(transactions, cls=mt940.JSONEncoder))

    assert len(decoded['transactions']) == len(transactions)
    # Balance -> nested dict; Amount -> Decimal as str; Date -> ISO str
    assert decoded['final_opening_balance'] == {
        'status': 'C',
        'amount': {'amount': '3236.28', 'currency': 'EUR'},
        'date': '2011-05-22',
    }
    # Every transaction amount is a Decimal serialised to a plain string.
    for transaction in decoded['transactions']:
        assert isinstance(transaction['amount']['amount'], str)
        assert isinstance(transaction['date'], str)


def test_json_round_trip_sum_amount_and_datetime() -> None:
    """``SumAmount`` (with its entry ``number``) and ``DateTime`` serialise.

    The mBank ``:90D:``/``:90C:`` and ``:13D:`` tags produce ``SumAmount`` and
    ``DateTime`` objects that never appear in the jejik ``.sta`` fixtures used
    by ``test_json_dump``'s value-free smoke check.
    """
    transactions = mt940.parse(str(_tests_path / 'mBank' / 'mt942.sta'))
    decoded = json.loads(json.dumps(transactions, cls=mt940.JSONEncoder))

    assert decoded['sum_credit_entries'] == {
        'amount': '0.03',
        'currency': 'PLN',
        'number': '3',
    }
    # The :13D: DateTime (with a +0100 FixedOffset) renders as an ISO string,
    # carrying the timezone offset, not a mapping.
    assert decoded['date'] == '2017-01-19 18:15:00+01:00'


def test_json_round_trip_asnb_non_swift_statement() -> None:
    """The opt-in ``StatementASNB`` tag output also round-trips cleanly.

    ASN fixtures live in ``.txt`` files and require a custom tag, so they are
    outside ``test_json_dump``'s ``.sta`` glob entirely.
    """
    tag = mt940.tags.StatementASNB()
    transactions = mt940.models.Transactions(tags={tag.id: tag})
    with (_tests_path / 'ASNB' / 'mt940.txt').open() as fh:
        transactions.parse(fh.read())

    decoded = json.loads(json.dumps(transactions, cls=mt940.JSONEncoder))
    assert len(decoded['transactions']) == len(transactions)
    assert decoded['transactions'][0]['amount'] == {
        'amount': '-65.00',
        'currency': 'EUR',
    }


def test_date_fixup_non_leap_february_clamped() -> None:
    """A Feb 29 value date in a non-leap year is clamped to Feb 28.

    ``test_date_fixup_pre_processor`` only covers Feb 30 in a leap year
    (``february_30.sta``, 2016 -> Feb 29); the non-leap clamp path was
    previously unexercised.
    """
    data = (
        ':20:REF\n'
        ':25:123456789\n'
        ':28C:0\n'
        ':60F:C170201EUR100,00\n'
        ':61:1702290228DR6,00N024NONREF\n'
        ':86:free\n'
        ':62F:C170228EUR94,00\n'
    )
    transactions = mt940.parse(data)
    assert transactions[0].data['date'] == mt940.models.Date(2017, 2, 28)


@pytest.mark.parametrize(
    ('detail', 'expected_purpose'),
    [
        # A literal '+' inside the first characters of free text (e.g. a
        # company name like "AB+...") must not be treated as a GVC KEYWORD+
        # separator: EREF is a real GVC key later in the text, so gvcodes runs.
        ('020?20AB+EREF', 'AB+EREF'),
        # 'A+B' at the very start must survive; SVWZ triggers gvcodes parsing.
        ('020?20A+B SVWZ TEXT', 'A+B SVWZ TEXT'),
    ],
)
def test_gvcode_leading_plus_in_free_text_kept_in_purpose(
    detail: str, expected_purpose: str
) -> None:
    """A '+' earlier than position 4 cannot terminate a GVC keyword.

    GVC keywords are 3-4 chars followed by '+'. ``_parse_mt940_gvcodes`` sliced
    ``purpose[index - 4:index]`` without a lower bound, so a '+' at index < 4
    produced a wrapped/empty slice matching the empty-string GVC key and
    truncated the purpose (dropping the leading free text before the '+').
    """
    data = (
        ':20:REF\n'
        ':25:123456789\n'
        ':28C:0\n'
        ':60F:C200101EUR100,00\n'
        ':61:2001010101C10,00NTRFNONREF\n'
        f':86:{detail}\n'
        ':62F:C200101EUR110,00\n'
    )
    transaction = mt940.parse(data)[0].data
    assert transaction['purpose'] == expected_purpose


def _two_structured_86_data(first_detail: str, second_detail: str) -> str:
    return (
        ':20:REF\n'
        ':25:123456789\n'
        ':28C:0\n'
        ':60F:C200101EUR100,00\n'
        ':61:2001010101C10,00NTRFNONREF\n'
        f':86:{first_detail}\n'
        f':86:{second_detail}\n'
        ':62F:C200101EUR110,00\n'
    )


@pytest.mark.parametrize(
    ('first_detail', 'second_detail', 'expected_purpose', 'expected_posting'),
    [
        # The second tag's None sub-fields clobber the first tag's real
        # values under the current (golden-pinned) merge semantics: the last
        # structured :86: wins per key, even with None.
        ('020?20REALPURPOSE', '020?00POSTINGTEXT', None, 'POSTINGTEXT'),
        ('020?00POSTINGTEXT', '020?20REALPURPOSE', 'REALPURPOSE', None),
    ],
)
def test_repeated_structured_86_merges_without_crash(
    first_detail: str,
    second_detail: str,
    expected_purpose: str | None,
    expected_posting: str | None,
) -> None:
    """Two structured ``:86:`` tags on one ``:61:`` must not crash the parse.

    A structured ``:86:`` emits every ``DETAIL_KEYS`` value including ``None``
    for absent sub-fields; a second structured ``:86:`` then hit
    ``None += str`` in ``_update_transaction`` (``TypeError`` aborting the
    whole file) in either order. This pins the CURRENT post-fix merge
    contract: a later string replaces an existing ``None``, while a later
    ``None`` still overwrites an earlier real value (the semantics the
    real-bank goldens encode -- see the xfail below for the pending
    preservation question).
    """
    transaction = mt940.parse(
        _two_structured_86_data(first_detail, second_detail)
    )[0].data
    assert transaction['purpose'] == expected_purpose
    assert transaction['posting_text'] == expected_posting


@pytest.mark.xfail(
    strict=True,
    reason='repeated structured :86: None-clobber semantics -- pending '
    'decision (audit task 7 review): preserving non-None values against a '
    "later tag's None is arguably more correct, but the same rule stops a "
    'structured :86: from nulling the customer_reference set by :61:, '
    'changing 5 real-bank goldens.',
)
def test_repeated_structured_86_preserves_real_values() -> None:
    """Preservation ideal: real values from BOTH tags survive, either order."""
    for first, second in [
        ('020?20REALPURPOSE', '020?00POSTINGTEXT'),
        ('020?00POSTINGTEXT', '020?20REALPURPOSE'),
    ]:
        transaction = mt940.parse(_two_structured_86_data(first, second))[
            0
        ].data
        assert transaction['purpose'] == 'REALPURPOSE'
        assert transaction['posting_text'] == 'POSTINGTEXT'
