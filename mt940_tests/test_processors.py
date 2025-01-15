import os
import pathlib
import typing

import mt940
import pytest
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
        processors=dict(
            pre_statement=[
                mt940.processors.date_fixup_pre_processor,
            ],
        )
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
        processors=dict(
            pre_final_closing_balance=[
                mt940.processors.add_currency_pre_processor('USD'),
            ],
            pre_final_opening_balance=[
                mt940.processors.add_currency_pre_processor('EUR'),
            ],
        )
    )
    transactions.parse(sta_data)
    assert transactions.data['final_closing_balance'].amount.currency == 'USD'
    assert transactions.data['final_opening_balance'].amount.currency == 'EUR'


def test_post_processor(sta_data: str) -> None:
    transactions = mt940.models.Transactions(
        processors=dict(
            post_closing_balance=[
                mt940.processors.date_cleanup_post_processor,
            ],
        )
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
        processors=dict(
            post_transaction_details=[
                mt940.processors.mBank_set_transaction_code,
                mt940.processors.mBank_set_iph_id,
                mt940.processors.mBank_set_tnr,
            ],
        )
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
        processors=dict(
            post_transaction_details=[
                mt940.processors.transaction_details_post_processor_with_space,
            ],
        ),
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
        processors=dict(
            post_transaction_details=[
                mt940.processors.mBank_set_tnr,
            ],
        )
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
