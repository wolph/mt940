import re
import decimal
import datetime
import collections

from . import processors
from . import _compat
import mt940


class Model(object):
    pass


class Date(datetime.date, Model):
    '''Just a regular date object which supports dates given as strings

    Args:
        year (str): The year (0-100), will automatically add 2000 when needed
        month (str): The month
        day (str): The day
    '''
    def __new__(cls, *args, **kwargs):
        if kwargs:
            year = kwargs.get('year')
            month = kwargs.get('month')
            day = kwargs.get('day')
            year = int(year, 10)
            if year < 1000:
                year += 2000

            month = int(month, 10)
            day = int(day, 10)
            return datetime.date.__new__(cls, year, month, day)
        else:
            # For pickling the date object uses it's own binary format
            # No need to do anything special there :)
            return datetime.date.__new__(cls, *args, **kwargs)


class Amount(Model):
    '''Amount object containing currency and amount

    Args:
        amount (str): Amount using either a , or a . as decimal separator
        status (str): Either C or D for credit or debit respectively
        currency (str): A 3 letter currency (e.g. EUR)

    >>> Amount('123.45', 'C', 'EUR')
    <123.45 EUR>
    >>> Amount('123.45', 'D', 'EUR')
    <-123.45 EUR>
    '''
    def __init__(self, amount, status, currency=None, **kwargs):
        self.amount = decimal.Decimal(amount.replace(',', '.'))
        self.currency = currency

        # C = credit, D = debit
        if status == 'D':
            self.amount = -self.amount

    def __repr__(self):
        return '<%s %s>' % (
            self.amount,
            self.currency,
        )


class Balance(Model):
    '''Parse balance statement

    Args:
        status (str): Either C or D for credit or debit respectively
        amount (Amount): Object containing the amount and currency
        date (date): The balance date

    >>> balance = Balance('C', '0.00', Date(2010, 7, 22))
    >>> balance.status
    'C'
    >>> balance.amount.amount
    Decimal('0.00')
    >>> isinstance(balance.date, Date)
    True
    >>> balance.date.year, balance.date.month, balance.date.day
    (2010, 7, 22)

    >>> Balance()
    <None @ None>
    '''
    def __init__(self, status=None, amount=None, date=None, **kwargs):
        if amount and not isinstance(amount, Amount):
            amount = Amount(amount, status, kwargs.get('currency'))
        self.status = status
        self.amount = amount
        self.date = date

    def __repr__(self):
        return '<%s>' % self

    def __str__(self):
        return '%s @ %s' % (
            self.amount,
            self.date,
        )


class Transactions(collections.Sequence):
    '''
    Collection of :py:class:`Transaction` objects with global properties such
    as begin and end balance

    '''

    #: Using the processors you can pre-process data before creating objects
    #: and modify them after creating the objects
    DEFAULT_PROCESSORS = dict(
        pre_account_identification=[],
        post_account_identification=[],
        pre_available_balance=[],
        post_available_balance=[],
        pre_closing_balance=[],
        post_closing_balance=[],
        pre_intermediate_closing_balance=[],
        post_intermediate_closing_balance=[],
        pre_final_closing_balance=[],
        post_final_closing_balance=[],
        pre_forward_available_balance=[],
        post_forward_available_balance=[],
        pre_opening_balance=[],
        post_opening_balance=[],
        pre_intermediate_opening_balance=[],
        post_intermediate_opening_balance=[],
        pre_final_opening_balance=[],
        post_final_opening_balance=[],
        pre_related_reference=[],
        post_related_reference=[],
        pre_statement=[processors.date_fixup_pre_processor],
        post_statement=[processors.date_cleanup_post_processor],
        pre_statement_number=[],
        post_statement_number=[],
        pre_non_swift=[],
        post_non_swift=[],
        pre_transaction_details=[],
        post_transaction_details=[],
        pre_transaction_reference_number=[],
        post_transaction_reference_number=[],
    )

    def __init__(self, processors=None):
        self.processors = self.DEFAULT_PROCESSORS.copy()
        if processors:
            self.processors.update(processors)

        self.transactions = []
        self.data = {}

    @property
    def currency(self):
        balance = mt940.utils.coalesce(
            self.data.get('final_opening_balance'),
            self.data.get('opening_balance'),
            self.data.get('intermediate_opening_balance'),
            self.data.get('available_balance'),
            self.data.get('forward_available_balance'),
            self.data.get('final_closing_balance'),
            self.data.get('closing_balance'),
            self.data.get('intermediate_closing_balance'),
        )
        if balance:
            return balance.amount.currency

    @classmethod
    def strip(cls, lines):
        for line in lines:
            # We don't like carriage returns in case of Windows files so let's
            # just replace them with nothing
            line = line.replace('\r', '')

            # Strip trailing whitespace from lines since they cause incorrect
            # files
            line = line.rstrip()

            # Skip separators
            if line.strip() == '-':
                continue

            # Return actual lines
            if line:
                yield line

    def parse(self, data):
        '''Parses mt940 data, expects a string with data

        Args:
            data (str): The MT940 data

        Returns: :py:class:`list` of :py:class:`Transaction`
        '''
        # Remove extraneous whitespace and such
        data = '\n'.join(self.strip(data.split('\n')))

        # The pattern is a bit annoying to match by regex, even with a greedy
        # match it's difficult to get both the beginning and the end so we're
        # working around it in a safer way to get everything.
        tag_re = re.compile(
            r'^:(?P<full_tag>(?P<tag>[0-9]{2}|NS)(?P<sub_tag>[A-Z])?):',
            re.MULTILINE)
        matches = list(tag_re.finditer(data))

        transaction = Transaction(self)
        self.transactions.append(transaction)

        for i, match in enumerate(matches):
            tag_id = match.group('tag')
            # Since non-digit tags exist, make the conversion optional
            if tag_id.isdigit():
                tag_id = int(tag_id)

            assert tag_id in mt940.tags.TAG_BY_ID, 'Unknown tag %r' \
                'in line: %r' % (tag_id, match.group(0))

            tag = mt940.tags.TAG_BY_ID.get(match.group('full_tag')) \
                or mt940.tags.TAG_BY_ID[tag_id]

            # Nice trick to get all the text that is part of this tag, python
            # regex matches have a `end()` and `start()` to indicate the start
            # and end index of the match.
            if matches[i + 1:]:
                tag_data = data[match.end():matches[i + 1].start()].strip()
            else:
                tag_data = data[match.end():].strip()

            tag_dict = tag.parse(self, tag_data)

            # Preprocess data before creating the object
            for processor in self.processors.get('pre_%s' % tag.slug):
                tag_dict = processor(self, tag, tag_dict)

            result = tag(self, tag_dict)

            # Postprocess the object
            for processor in self.processors.get('post_%s' % tag.slug):
                result = processor(self, tag, tag_dict, result)

            # Creating a new transaction for :20: and :61: tags allows the
            # tags from :20: to :61: to be captured as part of the transaction.
            if isinstance(tag, mt940.tags.TransactionReferenceNumber) or \
                    isinstance(tag, mt940.tags.Statement):
                # Transactions only get a Transaction Reference Code ID from a
                # :61: tag which is why a new transaction is created if the
                # 'id' has a value.
                if transaction.data.get('id'):
                    transaction = Transaction(self, result)
                    self.transactions.append(transaction)
                else:
                    transaction.data.update(result)
            elif tag.scope is Transaction:
                # Combine multiple results together as one string, Rabobank has
                # multiple :86: tags for a single transaction
                for k, v in _compat.iteritems(result):
                    if k in transaction.data and hasattr(v, 'strip'):
                        transaction.data[k] += '\n%s' % v.strip()
                    else:
                        transaction.data[k] = v

            elif tag.scope is Transactions:  # pragma: no branch
                self.data.update(result)

        return self.transactions

    def __getitem__(self, key):
        return self.transactions[key]

    def __len__(self):
        return len(self.transactions)

    def __repr__(self):
        return '<%s[%s]>' % (
            self.__class__.__name__,
            ']['.join('%s: %s' % (k.replace('_balance', ''), v)
                      for k, v in _compat.iteritems(self.data)
                      if k.endswith('balance'))
        )


class Transaction(Model):
    def __init__(self, transactions, data=None):
        self.transactions = transactions
        self.data = {}
        self.update(data)

    def update(self, data):
        if data:
            self.data.update(data)

    def __repr__(self):
        return '<%s[%s] %s>' % (
            self.__class__.__name__,
            self.data.get('date'),
            self.data.get('amount'),
        )

