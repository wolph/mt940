import pytest
import mt940
from mt940.tags import Tag


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
