import pytest
import mt940
from mt940.tags import Tag, StatementASNB
import pprint


@pytest.fixture
def long_statement_number():
    with open('mt940_tests/self-provided/long_statement_number.sta') as fh:
        return fh.read()


class MyStatementNumber(Tag):

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
    tag_parser = StatementASNB()
    trs = mt940.models.Transactions(tags={
        tag_parser.id: tag_parser
    })

    trs.parse(ASNB_mt940_data)
    trs_data = pprint.pformat(trs.data, sort_dicts=False)
    assert trs_data == """{'transaction_reference': '0000000000',
 'account_identification': 'NL81ASNB9999999999',
 'statement_number': '31',
 'sequence_number': '1',
 'final_opening_balance': <<404.81 EUR> @ 2020-01-31>,
 'final_closing_balance': <<501.23 EUR> @ 2020-01-31>}"""
    assert len(trs) == 8
    # test first entry
    td = trs.transactions[0].data.pop('transaction_details')
    assert pprint.pformat(trs.transactions[0].data, sort_dicts=False) == \
        """{'status': 'D',
 'funds_code': None,
 'amount': <-65.00 EUR>,
 'id': 'NOVB',
 'customer_reference': 'NL47INGB9999999999',
 'bank_reference': None,
 'extra_details': 'hr gjlm paulissen',
 'currency': 'EUR',
 'date': Date(2020, 1, 1),
 'entry_date': Date(2020, 1, 1),
 'guessed_entry_date': Date(2020, 1, 1)}"""
    assert td == 'NL47INGB9999999999 hr gjlm paulissen\nBetaling sieraden'
    assert str(trs.transactions[1].data['amount']) == '<1000.00 EUR>'
    assert str(trs.transactions[2].data['amount']) == '<-801.55 EUR>'
    assert str(trs.transactions[3].data['amount']) == '<-1.65 EUR>'
    assert str(trs.transactions[4].data['amount']) == '<828.72 EUR>'
    assert str(trs.transactions[5].data['amount']) == '<-1000.00 EUR>'
    assert str(trs.transactions[6].data['amount']) == '<1000.18 EUR>'
    td = trs.transactions[7].data.pop('transaction_details')
    assert pprint.pformat(trs.transactions[7].data, sort_dicts=False) == \
        """{'status': 'D',
 'funds_code': None,
 'amount': <-903.76 EUR>,
 'id': 'NIDB',
 'customer_reference': 'NL08ABNA9999999999',
 'bank_reference': None,
 'extra_details': 'international card services',
 'currency': 'EUR',
 'date': Date(2020, 1, 31),
 'entry_date': Date(2020, 1, 31),
 'guessed_entry_date': Date(2020, 1, 31)}"""
    assert td[0:46] == 'NL08ABNA9999999999 international card services'
    assert td[47:112] == \
        '000000000000000000000000000000000 0000000000000000 Betaling aan I'
    assert td[113:176] == \
        'CS 99999999999 ICS Referentie: 2020-01-31 21:27 000000000000000'

