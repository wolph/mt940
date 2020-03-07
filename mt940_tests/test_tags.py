import pytest
import mt940
from mt940 import tags
from mt940 import models
import pprint


@pytest.fixture
def long_statement_number():
    with open('mt940_tests/self-provided/long_statement_number.sta') as fh:
        return fh.read()


class MyStatementNumber(tags.Tag):

    '''Statement number / sequence number

    Pattern: 10n
    '''
    id = 28
    pattern = r'''
    (?P<statement_number>\d{1,10})  # 10n
    $'''


def test_specify_different_tag_classes(long_statement_number):
    tag_parser = MyStatementNumber()
    transactions = mt940.models.Transactions(tags={
        tag_parser.id: tag_parser
    })
    transactions.parse(long_statement_number)
    assert transactions.data.get('statement_number') == '1810118101'


@pytest.fixture
def ASNB_mt940_data():
    with open('mt940_tests/ASNB/0708271685_09022020_164516.940.txt') as fh:
        return fh.read()


def test_ASNB_tags(ASNB_mt940_data):
    tag_parser = tags.StatementASNB()
    trs = mt940.models.Transactions(tags={
        tag_parser.id: tag_parser
    })

    trs.parse(ASNB_mt940_data)

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

    pprint.pprint(trs.data)
    pprint.pprint(trs.data['final_opening_balance'])
    pprint.pprint(type(trs.data['final_opening_balance']))
    pprint.pprint(trs.data['final_opening_balance'].__dict__)

    assert trs.transactions[0].data == {
        'status': 'D',
        'funds_code': None,
        'amount': models.Amount('65.00', 'D', 'EUR'),
        'id': 'NOVB',
        'customer_reference': 'NL47INGB9999999999',
        'bank_reference': None,
        'extra_details': 'hr gjlm paulissen',
        'currency': 'EUR',
        'date': models.Date(2020, 1, 1),
        'entry_date': models.Date(2020, 1, 1),
        'guessed_entry_date': models.Date(2020, 1, 1),
    }

    assert td == 'NL47INGB9999999999 hr gjlm paulissen\nBetaling sieraden'
    assert trs.transactions[1].data['amount'] == models.Amount(
        '1000.00', 'C', 'EUR')
    assert trs.transactions[2].data['amount'] == models.Amount(
        '801.55', 'D', 'EUR')
    assert trs.transactions[3].data['amount'] == models.Amount(
        '1.65', 'D', 'EUR')
    assert trs.transactions[4].data['amount'] == models.Amount(
        '828.72', 'C', 'EUR')
    assert trs.transactions[5].data['amount'] == models.Amount(
        '1000.00', 'D', 'EUR')
    assert trs.transactions[6].data['amount'] == models.Amount(
        '1000.18', 'C', 'EUR')

    td = trs.transactions[7].data.pop('transaction_details')
    assert trs.transactions[7].data == {
        'status': 'D',
        'funds_code': None,
        'amount': models.Amount('903.76', 'D', 'EUR'),
        'id': 'NIDB',
        'customer_reference': 'NL08ABNA9999999999',
        'bank_reference': None,
        'extra_details': 'international card services',
        'currency': 'EUR',
        'date': models.Date(2020, 1, 31),
        'entry_date': models.Date(2020, 1, 31),
        'guessed_entry_date': models.Date(2020, 1, 31),
    }
    assert td[0:46] == 'NL08ABNA9999999999 international card services'
    assert td[47:112] == \
        '000000000000000000000000000000000 0000000000000000 Betaling aan I'
    assert td[113:176] == \
        'CS 99999999999 ICS Referentie: 2020-01-31 21:27 000000000000000'

