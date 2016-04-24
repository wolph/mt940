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


