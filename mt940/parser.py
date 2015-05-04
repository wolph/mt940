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
import decimal
import datetime
import collections

#: ABN-AMRO/Rabo `format`_: `6!n[4!n]2a[1!a]15d1!a3!c16x[//16x]`
TRANSACTION_DATA_RE = re.compile(
    r'''^
    (?P<year>\d{2})  # 6!n Value Date (YYMMDD)
    (?P<month>\d{2})
    (?P<day>\d{2})
    (?P<booking_date>\d{4})?  # [4!n] Entry Date (MMDD)
    (?P<direction>[A-Z]?[DC])  # 2a Debit/Credit Mark
    (?P<funds_code>[A-Z])? # [1!a] Funds Code (3rd character of the currency
                           # code, if needed)
    (?P<amount>[\d,]{1,15})  # 15d Amount
    (?P<id>[A-Z][A-Z0-9]{3})?  # 1!a3!c Transaction Type Identification Code
    (?P<customer_reference>.{0,16})  # 16x Customer Reference
    (//(?P<bank_reference>.{0,16}))?  # [//16x] Bank Reference
    (?P<extra_details>.{0,34})  # [34x] Supplementary Details (this will be on
                                # a new/separate line)
    ''', re.VERBOSE | re.IGNORECASE)


#: Rabo `format`_: `6*65x`
TRANSACTION_DETAIL_RABO_RE = re.compile(
    r'''^
    /ORDP/
    /NAME/(?P<name>[^/]{0,70})
    ''', re.VERBOSE)


#: Balance `format`_: `1!a6!n3!a15d`
BALANCE_RE = re.compile(
    r'''^
    (?P<status>[DC])  # 1!a Debit/Credit
    (?P<year>\d{2})  # 6!n Value Date (YYMMDD)
    (?P<month>\d{2})
    (?P<day>\d{2})
    (?P<currency>.{3})  # 3!a Currency
    (?P<amount>[0-9,]{0,16})  # 15d Amount (includes decimal sign, so 16)
    $''', re.VERBOSE | re.IGNORECASE)


class Transactions(collections.Sequence):
    '''
    Collection of :py:class:`Transaction` objects with global properties such as
    begin and end balance

    '''

    def __init__(self):
        self.transactions = []
        self.opening_balance = Balance() #: Opening balance
        self.available_balance = Balance() #: Available balance
        self.closing_balance = Balance() #: Closing balance

    def parse(self, data):
        '''Parses mt940 data, expects a string with data

        :param str data: The MT940 data
        :rtype: :py:class:`list` of :py:class:`Transaction`
        '''
        # We don't like carriage returns in case of Windows files so let's just
        # replace them with nothing
        data = data.replace('\r', '')

        # The transaction collections are separated by a '-'
        transaction = None
        transaction_collections = data.split('\n-\n')
        for transaction_collection in transaction_collections:
            for transaction in Transaction.parse(transaction_collection):
                self.transactions.append(transaction)

        if transaction:
            self.opening_balance = transaction.opening_balance
            self.available_balance = transaction.available_balance
            self.closing_balance = transaction.closing_balance

        return self.transactions

    def __getitem__(self, key):
        return self.transactions[key]

    def __len__(self):
        return len(self.transactions)


class Balance(object):
    def __init__(self, status, amount, date):
        self.status = status
        self.amount = amount
        self.date = date


class Transaction(object):
    _TRANSACTION = 61
    _TRANSACTION_DETAILS = 86
    _ACCOUNT_NUMBER = 25
    _STATEMENT_NUMBER = 28
    _OPENING_BALANCE = 60
    _CLOSING_BALANCE = 62
    _AVAILABLE_BALANCE = 64

    method_re = re.compile(
        r':(?P<field_number>[0-9]{2})(?P<field_name>[A-Z])?:')

    def __init__(self, transaction=None, data=None, details=None):
        self.amount = 0
        self.items = dict()

        if transaction and data and details:
            # Update the dictionary with values from the given transaction
            vars(self).update(vars(transaction))
            self.handle_transaction_data(data)
            self.handle_transaction_details(details)

    def get(self, key, default=None):
        '''Get a property from the transaction with optional default value'''
        return getattr(self, key, default)

    @classmethod
    def parse(cls, data):
        data = '\n'.join(data.split('\n')[3:])
        transaction = Transaction()
        transactions = []
        transactions_detail = []

        # The pattern is a bit annoying to match by regex, even with a greedy
        # match it's difficult to get both the beginning and the end so we're
        # working around it in a safer way to get everything.
        matches = list(cls.method_re.finditer(data))
        for i, match in enumerate(matches):
            field_number = int(match.group('field_number'))
            if matches[i + 1:]:
                match_data = data[match.end():matches[i + 1].start()].strip()
            else:
                match_data = data[match.end():].strip()

            method = cls.methods.get(field_number)
            if method:
                method(transaction, match_data)
            elif field_number is cls._TRANSACTION:
                transactions.append(match_data)
            elif field_number is cls._TRANSACTION_DETAILS:
                transactions_detail.append(match_data)

        for data, details in zip(transactions, transactions_detail):
            yield Transaction(transaction, data, details)

    def _handle_transaction_data(self, data):
        self.identifier = data
        match_result = TRANSACTION_DATA_RE.match(data)

        if not match_result:
            raise RuntimeError('Unknown format', data)

        match = match_result.groupdict()
        self.date = datetime.date(
            2000 + int(match['year'], 10),
            int(match['month'], 10),
            int(match['day'], 10),
        )
        amount = decimal.Decimal(match['amount'].replace(',', '.'))
        # C = credit, D = debit
        if match['direction'] == 'D':
            amount = -amount

        self.amount = amount

    def _handle_transaction_details(self, details):
        details = re.sub(r' {2,}', '  ', details)
        if details.startswith('SEPA'):
            details = details.split('\n')
            details = sum([re.split(r'\s{2,}', d) for d in details], [])
            details = [d.split(': ', 1) for d in details if ':' in d]
            items = dict((k.lower(), v) for k, v in details)

            if 'naam' in items:
                items['name'] = items.pop('naam')

        elif re.match('^/(TRTP|RTYP|ORDP|EREF|BENM)/', details):
            details = details.replace('\n', ' ')
            items = re.findall(r'/(?P<key>[A-Z]+)/\s*(?P<value>[^/]+)',
                               details)
            items = dict((k.lower(), v) for k, v in items)
        else:
            items = dict(description=details)

        self.items = items

    def _handle_account_number(self, account_number):
        self.account_number = account_number

    def _handle_statement_number(self, statement_number):
        self.statement_number = statement_number

    @classmethod
    def _to_date(self, year, month, day, **kwargs):
        return datetime.date(
            int(year, 10) + 2000,
            int(month, 10),
            int(day, 10),
        )

    @classmethod
    def parse_balance(cls, balance):
        '''Parse balance statement

        >>> Transaction.parse_balance('C100722EUR0,00') == {
        ...     'status': 'C',
        ...     'currency': 'EUR',
        ...     'amount': '0,00',
        ...     'year': '10',
        ...     'date': datetime.date(2010, 7, 22),
        ...     'day': '22',
        ...     'month': '07'}
        True
        '''
        results = dict()
        if balance:
            results.update(BALANCE_RE.match(balance).groupdict())
            results['date'] = datetime.date(
                2000 + int(results['year'], 10),
                int(results['month'], 10),
                int(results['day'], 10),
            )
        return results

    def _handle_opening_balance(self, opening_balance):
        self.opening_balance = self.parse_balance(opening_balance)

    def _handle_available_balance(self, available_balance):
        self.available_balance = self.parse_balance(available_balance)

    def _handle_closing_balance(self, closing_balance):
        self.closing_balance = self.parse_balance(closing_balance)

    methods = {
        _ACCOUNT_NUMBER: _handle_account_number,
        _STATEMENT_NUMBER: _handle_statement_number,
        _OPENING_BALANCE: _handle_opening_balance,
        _AVAILABLE_BALANCE: _handle_available_balance,
        _CLOSING_BALANCE: _handle_closing_balance,
    }

    def __repr__(self):
        if self.get('amount') >= 0:
            from_ = self.get('name')
            to = self.get('account_number')
            amount = self.get('amount', 0)
        else:
            to = self.get('name')
            from_ = self.get('account_number')
            amount = -self.get('amount', 0)

        return '<%s[%s] %s -> %s: %s>' % (
            self.__class__.__name__,
            self.get('date'),
            from_,
            to,
            amount,
        )


def parse(fh):
    '''
    Parses mt940 data and returns transactions object

    :param file or str fh: file handler or filename to read
    :return: Collection of transactions
    :rtype: Transactions
    '''
    if not hasattr(fh, 'read'):
        fh = open(fh)
    data = fh.read()

    transactions = Transactions()
    transactions.parse(data)
    return transactions

