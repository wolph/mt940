# vim: fileencoding=utf-8:
import re
import decimal
import datetime


class Transactions(object):
    def __init__(self, fh):
        self.fh = fh

    def __iter__(self):
        # Get the data
        data = self.fh.read()
        # We don't like carriage returns in case of Windows files so let's just
        # replace them with nothing
        data = data.replace('\r', '')

        # The transaction collections are separated by a '-'
        transaction_collections = data.split('\n-\n')
        for transaction_collection in transaction_collections:
            for transaction in Transaction.parse(transaction_collection):
                yield transaction


class Transaction(object):
    TRANSACTION = 61
    TRANSACTION_DETAILS = 86
    ACCOUNT_NUMBER = 25
    STATEMENT_NUMBER = 28
    OPENING_BALANCE = 60
    CLOSING_BALANCE = 62
    AVAILABLE_BALANCE = 64

    method_re = re.compile(
        r':(?P<field_number>[0-9]{2})(?P<field_name>[A-Z])?:')

    def __repr__(self):
        if self.amount >= 0:
            from_ = self.other
            to = self.account_number
            amount = self.amount
        else:
            to = self.other
            from_ = self.account_number
            amount = -self.amount

        return '<%s[%s] %s -> %s: %s>' % (
            self.__class__.__name__,
            self.date,
            from_,
            to,
            amount,
        )

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
            elif field_number is cls.TRANSACTION:
                transactions.append(match_data)
            elif field_number is cls.TRANSACTION_DETAILS:
                transactions_detail.append(match_data)

        for data, details in zip(transactions, transactions_detail):
            yield Transaction(transaction, data, details)

    def __init__(self, transaction=None, data=None, details=None):
        if transaction and data and details:
            # Update the dictionary with values from the given transaction
            vars(self).update(vars(transaction))
            self.handle_transaction_data(data)
            self.handle_transaction_details(details)

    def handle_transaction_data(self, data):
        self.identifier = data
        match = re.match(r'''^
            (?P<year>\d{2})
            (?P<month>\d{2})
            (?P<day>\d{2})
            (?P<booking_date>\d{4})
            (?P<direction>[DC])
            (?P<amount>[\d,]+)
        ''', data, re.VERBOSE).groupdict()
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

    def handle_transaction_details(self, details):
        details = re.sub(r' {2,}', '  ', details)
        if details.startswith('SEPA'):
            details = details.split('\n')
            details = sum([re.split(r'\s{2,}', d) for d in details], [])
            details = [d.split(': ', 1) for d in details if ':' in d]
            items = dict((k.lower(), v) for k, v in details)

            if 'naam' in items:
                items['name'] = items.pop('naam')
        elif details.startswith('/TRTP/') or details.startswith('/RTYP/'):
            details = details.replace('\n', ' ')
            items = re.findall(r'/(?P<key>[A-Z]+)/\s*(?P<value>[^/]+)',
                               details)
            items = dict((k.lower(), v) for k, v in items)
        elif re.match(r'^([BG]EA|CHIP)\s+', details):
            if 'NR:' in details:
                details = re.split(r'\s+', details.split('NR:', 1)[1], 2)
            else:
                details = re.split(r'\s+', details, 2)
                details[0] = ''
            date, amount = details[1].split('/', 1)
            date = [int(d, 10) for d in date.split('.')]
            card, name = details[2].split(',')
            items = dict(
                id=details[0],
                amount=amount,
                date=datetime.date(
                    2000 + date[2],
                    date[1],
                    date[0],
                ),
                name=name,
                card=card,
            )
        elif details.startswith('GIRO'):
            details = re.split(r'\s{2,}', details, 3)
            description, date = details[3].split('TRANSACTIEDATUM*')
            items = dict(
                number=details[1],
                name=details[2],
                description=description,
                date=date,
            )
        elif re.match(r'^\d{,3}\.\d{,3}\.\d{,3}\.\d{,3}\s{2,}', details):
            number, description = re.split(r'\s{2,}', details, 1)
            name, description = description.split('\n', 1)
            description, id_ = description.split('BETALINGSKENM.')
            items = dict(
                number=number.strip(),
                id=id_,
                description=description.strip(),
                name=name.strip(),
            )
        elif re.match(r'^\d{,3}\.\d{,3}\.\d{,3}\.\d{,3}\s', details):
            number, description = details.split(' ', 1)
            name, description = re.split(r'\s{2,}', description, 1)
            items = dict(
                number=number.strip(),
                description=description.strip(),
                name=name.strip(),
            )
        else:
            raise TypeError('Unknown transaction type, cannot parse %r' %
                            details)  # pragma: no cover

        self.items = items

    @property
    def other(self):
        out = []
        if self.items.get('number'):
            out.append('[%s]' % self.items['number'])
        out.append(self.items['name'])

        return ''.join(out)

    def handle_account_number(self, account_number):
        self.account_number = account_number

    def handle_statement_number(self, statement_number):
        self.statement_number = statement_number

    def handle_opening_balance(self, opening_balance):
        self.set_opening_balance = opening_balance

    def handle_available_balance(self, available_balance):
        self.set_available_balance = available_balance  # pragma: no cover

    def handle_closing_balance(self, closing_balance):
        self.set_closing_balance = closing_balance

    methods = {
        ACCOUNT_NUMBER: handle_account_number,
        STATEMENT_NUMBER: handle_statement_number,
        OPENING_BALANCE: handle_opening_balance,
        AVAILABLE_BALANCE: handle_available_balance,
        CLOSING_BALANCE: handle_closing_balance,
    }


def parse(fh):
    return Transactions(fh)

