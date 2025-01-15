# pyright: strict
"""
The MT940 format is a standard for bank account statements. It is used by
many banks in Europe and is based on the SWIFT MT940 format.

The MT940 tags are:

+---------+-----------------------------------------------------------------+
| Tag     | Description                                                     |
+=========+=================================================================+
| `:13:`  | Date/Time indication at which the report was created            |
+---------+-----------------------------------------------------------------+
| `:20:`  | Transaction Reference Number                                    |
+---------+-----------------------------------------------------------------+
| `:21:`  | Related Reference Number                                        |
+---------+-----------------------------------------------------------------+
| `:25:`  | Account Identification                                          |
+---------+-----------------------------------------------------------------+
| `:28:`  | Statement Number                                                |
+---------+-----------------------------------------------------------------+
| `:34:`  | The floor limit for debit and credit                            |
+---------+-----------------------------------------------------------------+
| `:60F:` | Opening Balance                                                 |
+---------+-----------------------------------------------------------------+
| `:60M:` | Intermediate Balance                                            |
+---------+-----------------------------------------------------------------+
| `:60E:` | Closing Balance                                                 |
+---------+-----------------------------------------------------------------+
| `:61:`  | Statement Line                                                  |
+---------+-----------------------------------------------------------------+
| `:62:`  | Closing Balance                                                 |
+---------+-----------------------------------------------------------------+
| `:62M:` | Intermediate Closing Balance                                    |
+---------+-----------------------------------------------------------------+
| `:62F:` | Final Closing Balance                                           |
+---------+-----------------------------------------------------------------+
| `:64:`  | Available Balance                                               |
+---------+-----------------------------------------------------------------+
| `:65:`  | Forward Available Balance                                       |
+---------+-----------------------------------------------------------------+
| `:86:`  | Transaction Information                                         |
+---------+-----------------------------------------------------------------+
| `:90:`  | Total number and amount of debit entries                        |
+---------+-----------------------------------------------------------------+
| `:NS:`  | Bank specific Non-swift extensions containing extra information |
+---------+-----------------------------------------------------------------+

Format
---------------------

Sources:

.. _Swift for corporates: http://www.sepaforcorporates.com/\
    swift-for-corporates/account-statement-mt940-file-format-overview/
.. _Rabobank MT940: https://www.rabobank.nl/images/\
    formaatbeschrijving_swift_bt940s_1_0_nl_rib_29539296.pdf

 - `Swift for corporates`_
 - `Rabobank MT940`_

The pattern for the tags use the following syntax:

::

    [] = optional
    ! = fixed length
    a = Text
    x = Alphanumeric, seems more like text actually. Can include special
        characters (slashes) and whitespace as well as letters and numbers
    d = Numeric separated by decimal (usually comma)
    c = Code list value
    n = Numeric
"""

from __future__ import annotations

import enum
import logging
import re
import typing

from . import models

logger = logging.getLogger(__name__)


class Tag:
    """
    Base Tag class for parsing and handling MT940 tag contents.
    """

    id: str | int = 0
    RE_FLAGS = re.IGNORECASE | re.VERBOSE | re.UNICODE
    scope: type[models.Transactions | models.Transaction] = models.Transactions
    pattern: str
    slug: str
    logger: logging.Logger

    def __init__(self) -> None:
        self.re = re.compile(self.pattern, self.RE_FLAGS)

    def parse(
        self, transactions: models.Transactions, value: str
    ) -> dict[str, str | None]:
        """
        Parses the given value using the Tag's pattern.

        :param transactions: The transactions model instance.
        :param value: The string value to parse.
        :return: A dictionary of matched group values.
        :raises RuntimeError: If parsing fails.
        """
        match = self.re.match(value)
        if match:  # pragma: no branch
            self.logger.debug(
                'matched (%d) %r against "%s", got: %s',
                len(value),
                value,
                self.pattern,
                match.groupdict(),
            )
            return match.groupdict()
        else:  # pragma: no cover
            self.logger.error(
                'matching id=%s (len=%d) "%s" against\n    %s',
                self.id,
                len(value),
                value,
                self.pattern,
            )
            self._debug_partial_match(value)
            raise RuntimeError(
                f'Unable to parse {self!r} from {value!r}', self, value
            )

    def _debug_partial_match(self, value: str) -> None:  # pragma: no cover
        """
        Helper function to debug partial matches against the pattern.
        """
        part_value = value
        for pattern in self.pattern.split('\n'):
            match = re.match(pattern, part_value, self.RE_FLAGS)
            if match:
                self.logger.info(
                    'matched %r against %r, got: %s',
                    pattern,
                    match.group(0),
                    match.groupdict(),
                )
                part_value = part_value[len(match.group(0)) :]
            else:
                self.logger.error(
                    'no match for %r against %r', pattern, part_value
                )

    def __call__(
        self, transactions: models.Transactions, value: dict[str, typing.Any]
    ) -> dict[str, typing.Any]:
        """
        Processes the tag value and returns parsed content.

        :param transactions: The transactions model instance.
        :param value: The string value to process.
        :return: The processed value, which can be a string or dict.
        """
        return value

    def __new__(cls, *args: typing.Any, **kwargs: typing.Any) -> Tag:
        """
        Creates a new Tag instance and sets up logging details.
        """
        cls.name = cls.__name__
        words = re.findall('([A-Z][a-z]+)', cls.__name__)
        cls.slug = '_'.join(w.lower() for w in words)
        cls.logger = logger.getChild(cls.name)
        return object.__new__(cls)

    def __hash__(self) -> int:
        """
        Returns a hash based on the tag's ID.

        :return: The integer hash of the tag.
        """
        return hash(self.id) if isinstance(self.id, str) else self.id


class DateTimeIndication(Tag):
    """Date/Time indication at which the report was created

    Pattern: 6!n4!n1! x4!n
    """

    id = 13
    pattern = r"""^
    (?P<year>\d{2})
    (?P<month>\d{2})
    (?P<day>\d{2})
    (?P<hour>\d{2})
    (?P<minute>\d{2})
    (\+(?P<offset>\d{4})|)
    """

    def __call__(
        self, transactions: models.Transactions, value: dict[str, typing.Any]
    ) -> dict[str, object]:
        data = super().__call__(transactions, value)
        return {'date': models.DateTime(**data)}


class TransactionReferenceNumber(Tag):
    """Transaction reference number

    Pattern: 16x
    """

    id = 20
    pattern = r'(?P<transaction_reference>.{0,16})'


class RelatedReference(Tag):
    """Related reference

    Pattern: 16x
    """

    id = 21
    pattern = r'(?P<related_reference>.{0,16})'


class AccountIdentification(Tag):
    """Account identification

    Pattern: 35x
    """

    id = 25
    pattern = r'(?P<account_identification>.{0,35})'


class StatementNumber(Tag):
    """Statement number / sequence number

    Pattern: 5n[/5n]
    """

    id = 28
    pattern = r"""
    (?P<statement_number>\d{1,5})  # 5n
    (?:/?(?P<sequence_number>\d{1,5}))?  # [/5n]
    $"""


class FloorLimitIndicator(Tag):
    """Floor limit indicator
    indicates the minimum value reported for debit and credit amounts

    Pattern: :34F:GHSC0,00
    """

    id = 34
    pattern = r"""^
    (?P<currency>[A-Z]{3})  # 3!a Currency
    (?P<status>[DC ]?)  # 2a Debit/Credit Mark
    (?P<amount>[0-9,]{0,16})  # 15d Amount (includes decimal sign, so 16)
    $"""

    def __call__(
        self, transactions: models.Transactions, value: dict[str, typing.Any]
    ) -> dict[str, object]:
        data = typing.cast(
            dict[str, str],
            super().__call__(transactions, value),
        )
        if data['status']:
            key = data['status'].lower() + '_floor_limit'
            return {key: models.Amount(**data)}
        data_d = data.copy()
        data_c = data.copy()
        data_d.update({'status': 'D'})
        data_c.update({'status': 'C'})
        return {
            'd_floor_limit': models.Amount(**data_d),
            'c_floor_limit': models.Amount(**data_c),
        }


class NonSwift(Tag):
    """Non-swift extension for MT940 containing extra information. The
    actual definition is not consistent between banks so the current
    implementation is a tad limited. Feel free to extend the implementation
    and create a pull request with a better version :)

    It seems this could be anything so we'll have to be flexible about it.

    Pattern: `2!n35x | *x`
    """

    scope = models.TransactionsAndTransaction
    id = 'NS'

    pattern = r"""
    (?P<non_swift>
        (
            (\d{2}.{0,})
            (\n\d{2}.{0,})*
        )|(
            [^\n]*
        )
    )
    $"""
    sub_pattern = r"""
    (?P<ns_id>\d{2})(?P<ns_data>.{0,})
    """
    sub_pattern_m = re.compile(
        sub_pattern, re.IGNORECASE | re.VERBOSE | re.UNICODE
    )

    def __call__(
        self, transactions: models.Transactions, value: dict[str, typing.Any]
    ) -> dict[str, object]:
        text: list[str] = []
        data = value['non_swift']
        for line in data.split('\n'):
            frag = self.sub_pattern_m.match(line)
            if frag and frag.group(2):
                ns = frag.groupdict()
                value['non_swift_' + ns['ns_id']] = ns['ns_data']
                text.append(ns['ns_data'])
            elif len(text) and text[-1]:
                text.append('')
            elif line.strip():
                text.append(line.strip())
        value['non_swift_text'] = '\n'.join(text)
        value['non_swift'] = data
        return value


class BalanceBase(Tag):
    """Balance base

    Pattern: 1!a6!n3!a15d
    """

    pattern = r"""^
    (?P<status>[DC])  # 1!a Debit/Credit
    (?P<year>\d{2})  # 6!n Value Date (YYMMDD)
    (?P<month>\d{2})
    (?P<day>\d{2})
    (?P<currency>.{3})  # 3!a Currency
    (?P<amount>[0-9,]{0,16})  # 15d Amount (includes decimal sign, so 16)
    """

    def __call__(
        self, transactions: models.Transactions, value: dict[str, typing.Any]
    ) -> dict[str, object]:
        data = super().__call__(transactions, value)
        data['amount'] = models.Amount(**data)
        data['date'] = models.Date(**data)
        return {self.slug: models.Balance(**data)}


class OpeningBalance(BalanceBase):
    id = 60


class FinalOpeningBalance(BalanceBase):
    id = '60F'


class IntermediateOpeningBalance(BalanceBase):
    id = '60M'


class Statement(Tag):
    """
    The MT940 Tag 61 provides information about a single transaction that
    has taken place on the account. Each transaction is identified by a
    unique transaction reference number (Tag 20) and is described in the
    Statement Line (Tag 61).

    Pattern: 6!n[4!n]2a[1!a]15d1!a3!c23x[//16x]

    The fields are:

     - `value_date`: transaction date (YYMMDD)
     - `entry_date`: Optional 4-digit month value and 2-digit day value of
       the entry date (MMDD) or 4 whitespace characters (some banks insert
       spaces here)
     - `funds_code`: Optional 1-character code indicating the funds type (
       the third character of the currency code if needed)
     - `amount`: 15-digit value of the transaction amount, including commas
       for decimal separation
     - `transaction_type`: Optional 4-character transaction type
       identification code starting with a letter followed by alphanumeric
       characters and spaces
     - `customer_reference`: Optional 16-character customer reference,
       excluding any bank reference
     - `bank_reference`: Optional 23-character bank reference starting with
       "//"
     - `supplementary_details`: Optional 34-character supplementary details
       about the transaction.

    The Tag 61 can occur multiple times within an MT940 file, with each
    occurrence representing a different transaction.
    """

    id = 61
    scope = models.Transaction
    pattern = r"""^
    (?P<year>\d{2})  # 6!n Value Date (YYMMDD)
    (?P<month>\d{2})
    (?P<day>\d{2})
    (?P<entry_month>\d{2}|\s{2})?  # [4!n] Entry Date (MMDD)
    (?P<entry_day>\d{2}|\s{2})?
    (?P<status>R?[DC])  # 2a Debit/Credit Mark
    (?P<funds_code>[A-Z])? # [1!a] Funds Code (3rd character of the currency
                            # code, if needed)
    [\n ]?
    (?P<amount>[\d,]{1,15})  # 15d Amount
    (?P<id>[A-Z][A-Z0-9 ]{3})?
    (?P<customer_reference>((?!//)[^\n]){0,16})
    (//(?P<bank_reference>.{0,23}))?
    (\n?(?P<extra_details>.{0,34}))?
    $"""

    def __call__(
        self, transactions: models.Transactions, value: dict[str, typing.Any]
    ) -> dict[str, object]:
        data = super().__call__(transactions, value)
        data.setdefault('currency', transactions.currency)
        data['amount'] = models.Amount(**data)
        date = data['date'] = models.Date(**data)

        entry_day = str(data.get('entry_day') or '')
        entry_month = str(data.get('entry_month') or '')

        if entry_day.isdigit() and entry_month.isdigit():
            entry_date = data['entry_date'] = models.Date(
                day=entry_day, month=entry_month, year=str(date.year)
            )
            if date > entry_date and (date - entry_date).days >= 330:
                year = 1
            elif entry_date > date and (entry_date - date).days >= 330:
                year = -1
            else:
                year = 0

            data['guessed_entry_date'] = models.Date(
                day=entry_date.day,
                month=entry_date.month,
                year=entry_date.year + year,
            )

        return data


class StatementASNB(Statement):
    """StatementASNB

    From: https://www.sepaforcorporates.com/swift-for-corporates

    Pattern: 6!n[4!n]2a[1!a]15d1!a3!c34x[//16x]
    [34x]

    But ASN bank puts the IBAN in the customer reference, which is according
    to Wikipedia at most 34 characters.

    So this is the new pattern:

    Pattern: 6!n[4!n]2a[1!a]15d1!a3!c34x[//16x]
    [34x]
    """

    pattern = r"""^
    (?P<year>\d{2})  # 6!n Value Date (YYMMDD)
    (?P<month>\d{2})
    (?P<day>\d{2})
    (?P<entry_month>\d{2}|\s{2})?
    (?P<entry_day>\d{2}|\s{2})?
    (?P<status>[A-Z]?[DC])
    (?P<funds_code>[A-Z])?
    \n?
    (?P<amount>[\d,]{1,15})
    (?P<id>[A-Z][A-Z0-9 ]{3})?
    (?P<customer_reference>.{0,34})
    (//(?P<bank_reference>.{0,16}))?
    (\n?(?P<extra_details>.{0,34}))?
    $"""

    def __call__(
        self, transactions: models.Transactions, value: dict[str, typing.Any]
    ) -> dict[str, object]:
        return super().__call__(transactions, value)


class ClosingBalance(BalanceBase):
    id: str | int = 62


class IntermediateClosingBalance(ClosingBalance):
    id = '62M'


class FinalClosingBalance(ClosingBalance):
    id = '62F'


class AvailableBalance(BalanceBase):
    id = 64


class ForwardAvailableBalance(BalanceBase):
    id = 65


class TransactionDetails(Tag):
    """Transaction details

    Pattern: 6x65x
    """

    id = 86
    scope = models.Transaction
    pattern = r"""
    (?P<transaction_details>(([\s\S]{0,65}\r?\n?){0,8}[\s\S]{0,65}))
    """


class SumEntries(Tag):
    """Number and Sum of debit Entries"""

    id: str | int = 90
    pattern = r"""^
    (?P<number>\d*)
    (?P<currency>.{3})  # 3!a Currency
    (?P<amount>[\d,]{1,15})  # 15d Amount
    """
    status: str

    def __call__(
        self, transactions: models.Transactions, value: dict[str, typing.Any]
    ) -> dict[str, object]:
        data = super().__call__(transactions, value)
        data['status'] = self.status
        return {self.slug: models.SumAmount(**data)}


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
