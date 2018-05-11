# vim: fileencoding=utf-8:
'''

Format
---------------------

Sources:

.. _Swift for corporates: http://www.sepaforcorporates.com/\
    swift-for-corporates/account-statement-mt940-file-format-overview/
.. _Rabobank MT940: https://www.rabobank.nl/images/\
    formaatbeschrijving_swift_bt940s_1_0_nl_rib_29539296.pdf

 - `Swift for corporates`_
 - `Rabobank MT940`_

::

    [] = optional
    ! = fixed length
    a = Text
    x = Alphanumeric, seems more like text actually. Can include special
        characters (slashes) and whitespace as well as letters and numbers
    d = Numeric separated by decimal (usually comma)
    c = Code list value
    n = Numeric
'''
import re
import pprint
import logging

try:
    import enum
except ImportError:  # pragma: no cover
    import sys
    print >> sys.stderr, 'MT940 requires the `enum34` package'

    class enum(object):
        @staticmethod
        def unique(*args, **kwargs):
            return []

        Enum = object

from . import models

logger = logging.getLogger(__name__)


class Tag(object):
    id = 0
    RE_FLAGS = re.IGNORECASE | re.VERBOSE | re.UNICODE
    scope = models.Transactions

    def __init__(self):
        self.re = re.compile(self.pattern, self.RE_FLAGS)

    def parse(self, transactions, value):
        match = self.re.match(value)
        if match:  # pragma: no branch
            self.logger.debug(
                'matched (%d) "%s" against "%s", got: %s',
                len(value), value, self.pattern,
                pprint.pformat(match.groupdict()))
        else:  # pragma: no cover
            self.logger.error(
                'matching (%d) "%s" against "%s"', len(value), value,
                self.pattern)

            part_value = value
            for pattern in self.pattern.split('\n'):
                match = re.match(pattern, part_value, self.RE_FLAGS)
                if match:
                    self.logger.info('matched "%s" against "%s", got: %s',
                                     pattern, match.group(0),
                                     pprint.pformat(match.groupdict()))
                    part_value = part_value[len(match.group(0)):]
                else:
                    self.logger.error('no match for "%s" against "%s"',
                                      pattern, part_value)

            raise RuntimeError(
                'Unable to parse "%s" from "%s"' % (self, value),
                self, value)
        return match.groupdict()

    def __call__(self, transactions, value):
        return value

    def __new__(cls, *args, **kwargs):
        cls.name = cls.__name__

        words = re.findall('([A-Z][a-z]+)', cls.__name__)
        cls.slug = '_'.join(w.lower() for w in words)
        cls.logger = logger.getChild(cls.name)

        return object.__new__(cls, *args, **kwargs)

    def __hash__(self):
        return self.id


class DateTimeIndication(Tag):
    '''Date/Time indication at which the report was created

    Pattern: 6!n4!n1! x4!n
    '''
    id = 13
    pattern = r'''^
    (?P<year>\d{2})
    (?P<month>\d{2})
    (?P<day>\d{2})
    (?P<hour>\d{2})
    (?P<minute>\d{2})
    (\+(?P<offset>\d{4})|)
    '''

    def __call__(self, transactions, value):
        data = super(DateTimeIndication, self).__call__(transactions, value)
        return {
            'date': models.DateTime(**data)
        }


class TransactionReferenceNumber(Tag):

    '''Transaction reference number

    Pattern: 16x
    '''
    id = 20
    pattern = r'(?P<transaction_reference>.{0,16})'


class RelatedReference(Tag):

    '''Related reference

    Pattern: 16x
    '''
    id = 21
    pattern = r'(?P<related_reference>.{0,16})'


class AccountIdentification(Tag):

    '''Account identification

    Pattern: 35x
    '''
    id = 25
    pattern = r'(?P<account_identification>.{0,35})'


class StatementNumber(Tag):

    '''Statement number / sequence number

    Pattern: 5n[/5n]
    '''
    id = 28
    pattern = r'''
    (?P<statement_number>\d{1,5})  # 5n
    (?:/?(?P<sequence_number>\d{1,5}))?  # [/5n]
    $'''


class FloorLimitIndicator(Tag):
    '''Floor limit indicator
    indicates the minimum value reported for debit and credit amounts

    Pattern: :34F:GHSC0,00
    '''
    id = 34
    pattern = r'''^
    (?P<currency>[A-Z]{3})  # 3!a Currency
    (?P<status>[DC]?)  # 2a Debit/Credit Mark
    (?P<amount>[0-9,]{0,16})  # 15d Amount (includes decimal sign, so 16)
    $'''

    def __call__(self, transactions, value):
        data = super(FloorLimitIndicator, self).__call__(transactions, value)
        if data['status']:
            return {
                data['status'].lower() + '_floor_limit': models.Amount(**data)
            }

        data_d = data.copy()
        data_c = data.copy()
        data_d.update({'status': 'D'})
        data_c.update({'status': 'C'})
        return {
            'd_floor_limit': models.Amount(**data_d),
            'c_floor_limit': models.Amount(**data_c)
        }


class NonSwift(Tag):

    '''Non-swift extension for MT940 containing extra information. The
    actual definition is not consistent between banks so the current
    implementation is a tad limited. Feel free to extend the implmentation
    and create a pull request with a better version :)

    Pattern: 2!n35x
    '''

    class scope(models.Transaction, models.Transactions):
        pass
    id = 'NS'

    pattern = r'''
    (?P<non_swift>
        (\d{2}.{0,})
        (\n\d{2}.{0,})*
    )
    $'''
    sub_pattern = r'''
    (?P<ns_id>\d{2})(?P<ns_data>.{0,})
    '''
    sub_pattern_m = re.compile(sub_pattern,
                               re.IGNORECASE | re.VERBOSE | re.UNICODE)

    def __call__(self, transactions, value):
        text = []
        data = value['non_swift']
        for line in data.split('\n'):
            frag = self.sub_pattern_m.match(line)
            if frag and frag.group(2):
                ns = frag.groupdict()
                value['non_swift_' + ns['ns_id']] = ns['ns_data']
                text.append(ns['ns_data'])
            elif len(text) and text[-1]:
                text.append('')
        value['non_swift_text'] = '\n'.join(text)
        value['non_swift'] = data
        return value


class BalanceBase(Tag):

    '''Balance base

    Pattern: 1!a6!n3!a15d
    '''
    pattern = r'''^
    (?P<status>[DC])  # 1!a Debit/Credit
    (?P<year>\d{2})  # 6!n Value Date (YYMMDD)
    (?P<month>\d{2})
    (?P<day>\d{2})
    (?P<currency>.{3})  # 3!a Currency
    (?P<amount>[0-9,]{0,16})  # 15d Amount (includes decimal sign, so 16)
    '''

    def __call__(self, transactions, value):
        data = super(BalanceBase, self).__call__(transactions, value)
        data['amount'] = models.Amount(**data)
        data['date'] = models.Date(**data)
        return {
            self.slug: models.Balance(**data)
        }


class OpeningBalance(BalanceBase):
    id = 60


class FinalOpeningBalance(BalanceBase):
    id = '60F'


class IntermediateOpeningBalance(BalanceBase):
    id = '60M'


class Statement(Tag):

    '''Statement

    Pattern: 6!n[4!n]2a[1!a]15d1!a3!c16x[//16x]
    '''
    id = 61
    scope = models.Transaction
    pattern = r'''^
    (?P<year>\d{2})  # 6!n Value Date (YYMMDD)
    (?P<month>\d{2})
    (?P<day>\d{2})
    (?P<entry_month>\d{2})?  # [4!n] Entry Date (MMDD)
    (?P<entry_day>\d{2})?
    (?P<status>[A-Z]?[DC])  # 2a Debit/Credit Mark
    (?P<funds_code>[A-Z])? # [1!a] Funds Code (3rd character of the currency
                            # code, if needed)
    (?P<amount>[\d,]{1,15})  # 15d Amount
    (?P<id>[A-Z][A-Z0-9 ]{3})?  # 1!a3!c Transaction Type Identification Code
    (?P<customer_reference>.{0,16})  # 16x Customer Reference
    (//(?P<bank_reference>.{0,16}))?  # [//16x] Bank Reference
    (\n?(?P<extra_details>.{0,34}))?  # [34x] Supplementary Details
    $'''

    def __call__(self, transactions, value):
        data = super(Statement, self).__call__(transactions, value)
        data.setdefault('currency', transactions.currency)

        data['amount'] = models.Amount(**data)
        data['date'] = models.Date(**data)

        if data.get('entry_day') and data.get('entry_month'):
            data['entry_date'] = models.Date(
                day=data.get('entry_day'),
                month=data.get('entry_month'),
                year=str(data['date'].year),
            )
        return data


class ClosingBalance(BalanceBase):
    id = 62


class FinalClosingBalance(ClosingBalance):
    id = '62F'


class IntermediateClosingBalance(ClosingBalance):
    id = '62M'


class AvailableBalance(BalanceBase):
    id = 64


class ForwardAvailableBalance(BalanceBase):
    id = 65


class TransactionDetails(Tag):

    '''Transaction details

    Pattern: 6x65x
    '''
    id = 86
    scope = models.Transaction
    pattern = r'''
    (?P<transaction_details>(([\s\S]{0,65}\r?\n?){0,8}[\s\S]{0,65}))
    '''


class SumEntries(Tag):
    '''Number and Sum of debit Entries

    '''

    id = 90
    pattern = r'''^
    (?P<number>\d+)
    (?P<currency>.{3})  # 3!a Currency
    (?P<amount>[\d,]{1,15})  # 15d Amount
    '''

    def __call__(self, transactions, value):
        data = super(SumEntries, self).__call__(transactions, value)

        data['status'] = self.status
        return {
            self.slug: models.SumAmount(**data)
        }


class SumDebitEntries(SumEntries):
    status = 'D'
    id = '90D'


class SumCreditEntries(SumEntries):
    status = 'C'
    id = '90C'


@enum.unique
class Tags(enum.Enum):
    DATE_TIME_INDICATION = DateTimeIndication()
    TRANSACTION_REFERENCE_NUMBER = TransactionReferenceNumber()
    RELATED_REFERENCE = RelatedReference()
    ACCOUNT_IDENTIFICATION = AccountIdentification()
    STATEMENT_NUMBER = StatementNumber()
    OPENING_BALANCE = OpeningBalance()
    INTERMEDIATE_OPENING_BALANCE = IntermediateOpeningBalance()
    FINAL_OPENING_BALANCE = FinalOpeningBalance()
    STATEMENT = Statement()
    CLOSING_BALANCE = ClosingBalance()
    INTERMEDIATE_CLOSING_BALANCE = IntermediateClosingBalance()
    FINAL_CLOSING_BALANCE = FinalClosingBalance()
    AVAILABLE_BALANCE = AvailableBalance()
    FORWARD_AVAILABLE_BALANCE = ForwardAvailableBalance()
    TRANSACTION_DETAILS = TransactionDetails()
    FLOOR_LIMIT_INDICATOR = FloorLimitIndicator()
    NON_SWIFT = NonSwift()
    SUM_ENTRIES = SumEntries()
    SUM_DEBIT_ENTRIES = SumDebitEntries()
    SUM_CREDIT_ENTRIES = SumCreditEntries()


TAG_BY_ID = {t.value.id: t.value for t in Tags}



