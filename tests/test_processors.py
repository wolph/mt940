import pytest
import mt940


@pytest.fixture
def sta_data():
    with open('tests/jejik/abnamro.sta') as fh:
        return fh.read()


@pytest.fixture
def february_30_data():
    with open('tests/self-provided/february_30.sta') as fh:
        return fh.read()


def test_date_fixup_pre_processor(february_30_data):
    transactions = mt940.models.Transactions(processors=dict(
        pre_statement=[
            mt940.processors.date_fixup_pre_processor,
        ],
    ))
    transactions.parse(february_30_data)
    assert transactions[0].data['date'] == mt940.models.Date(2016, 2, 29)


def test_parse_data():
    with open('tests/jejik/abnamro.sta') as fh:
        mt940.parse(fh.read())


def test_parse_fh():
    with open('tests/jejik/abnamro.sta') as fh:
        mt940.parse(fh)


def test_parse_filename():
    mt940.parse('tests/jejik/abnamro.sta')


def test_pre_processor(sta_data):
    transactions = mt940.models.Transactions(processors=dict(
        pre_final_closing_balance=[
            mt940.processors.add_currency_pre_processor('USD'),
        ],
        pre_final_opening_balance=[
            mt940.processors.add_currency_pre_processor('EUR'),
        ],
    ))

    transactions.parse(sta_data)
    assert transactions.data['final_closing_balance'].amount.currency == 'USD'
    assert transactions.data['final_opening_balance'].amount.currency == 'EUR'


def test_post_processor(sta_data):
    transactions = mt940.models.Transactions(processors=dict(
        post_closing_balance=[
            mt940.processors.date_cleanup_post_processor,
        ],
    ))

    transactions.parse(sta_data)
    assert 'closing_balance_day' not in transactions.data


@pytest.fixture
def mBank_mt942_data():
    with open('tests/mBank/mt942.sta') as fh:
        return fh.read()


def test_mBank_processors(mBank_mt942_data):
    transactions = mt940.models.Transactions(processors=dict(
        post_transaction_details=[
            mt940.processors.mBank_set_transaction_code,
            mt940.processors.mBank_set_iph_id,
            mt940.processors.mBank_set_tnr,
        ],
    ))

    transaction = transactions.parse(mBank_mt942_data)[0].data
    assert transaction['transaction_code'] == 911
    assert transaction['iph_id'] == '000000000001'
    assert transaction['tnr'] == '179171073864111.010001'


@pytest.fixture
def mBank_with_newline_in_tnr():
    with open('tests/mBank/with_newline_in_tnr.sta') as fh:
        return fh.read()


def test_mBank_set_tnr_parses_tnr_with_newlines(mBank_with_newline_in_tnr):
    transactions = mt940.models.Transactions(processors=dict(
        post_transaction_details=[
            mt940.processors.mBank_set_tnr,
        ],
    ))

    transactions_ = transactions.parse(mBank_with_newline_in_tnr)
    assert transactions_[0].data['tnr'] == '179301073837502.000001'
    assert transactions_[1].data['tnr'] == '179301073844398.000001'

