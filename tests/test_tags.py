import pytest
import mt940
from mt940.tags import Tag

@pytest.fixture
def long_statement_number():
    with open('tests/self-provided/long_statement_number.sta') as fh:
        return fh.read()

class MyStatementNumber(Tag):

    '''Statement number / sequence number

    Pattern: 10n
    '''
    id = 28
    pattern = r'''
    (?P<statement_number>\d{1,10})  # 10n
    $'''

def test_specify_different_tag_classes(february_30_data):
    transactions = mt940.models.Transactions(tags=dict(
        OPENING_BALANCE = MyStatementNumber()
    ))
    transactions.parse(long_statement_number)
    assert transactions[0].data['statement_numbes'] == ''
