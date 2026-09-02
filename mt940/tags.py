"""Tag parsers for the fields of an MT940 statement.

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
from typing import TYPE_CHECKING, ClassVar

from . import models
from .options import Options

if TYPE_CHECKING:
    from typing_extensions import Self

logger = logging.getLogger(__name__)

#: An entry date more than this many days away from the value date means the
#: two fall in different years, so the entry date's year needs correcting.
_YEAR_BOUNDARY_DAYS = 330

#: What 5.0.0 captured of a ``:86:`` value: up to nine chunks of at most 65
#: characters, each but the last optionally followed by a line break. Longer
#: details were silently cut off. The pattern accepts the empty string, so it
#: always matches.
_LEGACY_DETAILS_RE = re.compile(r'(?:[\s\S]{0,65}\r?\n?){0,8}[\s\S]{0,65}')


def _options_of(transactions: models.Transactions) -> Options:
    """Return the options of the collection being parsed.

    Tags are shared singletons, so the switches always come from
    ``transactions``. Callers that pass something without options, as older
    code did with ``None``, get the 5.0.0 defaults.

    Args:
        transactions: The collection being parsed.

    Returns:
        The options to honour.
    """
    options: object = getattr(transactions, 'options', None)
    return options if isinstance(options, Options) else Options()


class Tag:
    """Base Tag class for parsing and handling MT940 tag contents."""

    id: ClassVar[str | int] = 0
    RE_FLAGS: ClassVar[re.RegexFlag] = re.IGNORECASE | re.VERBOSE | re.UNICODE
    scope: ClassVar[type[models.Transactions | models.Transaction]] = (
        models.Transactions
    )
    pattern: ClassVar[str]
    name: ClassVar[str]
    slug: ClassVar[str]
    logger: ClassVar[logging.Logger]

    def __init__(self) -> None:
        """Compile the tag's ``pattern`` with :attr:`RE_FLAGS`."""
        self.re: re.Pattern[str] = re.compile(self.pattern, self.RE_FLAGS)

    def parse(
        self, transactions: models.Transactions, value: str
    ) -> dict[str, str | None]:
        """Parses the given value using the Tag's pattern.

        Args:
            transactions: The transactions model instance.
            value: The string value to parse.

        Returns:
            A dictionary of matched group values.

        Raises:
            RuntimeError: If the value does not match the tag's pattern.
        """
        # Part of the tag protocol, the base parser needs no context.
        del transactions
        match = self.re.match(value)
        if match:
            self.logger.debug(
                'matched (%d) %r against "%s", got: %s',
                len(value),
                value,
                self.pattern,
                match.groupdict(),
            )
            return match.groupdict()
        self.logger.error(
            'matching id=%s (len=%d) "%s" against\n    %s',
            self.id,
            len(value),
            value,
            self.pattern,
        )
        self._debug_partial_match(value)
        msg = f'Unable to parse {self!r} from {value!r}'
        raise RuntimeError(msg, self, value)

    def _debug_partial_match(self, value: str) -> None:
        """Helper function to debug partial matches against the pattern."""
        part_value = value
        for pattern in self.pattern.split('\n'):
            try:
                match = re.match(pattern, part_value, self.RE_FLAGS)
            except re.error:
                # Single lines of a pattern with multi-line groups are not
                # valid patterns on their own; skip them instead of masking
                # the RuntimeError raised by `parse`.
                self.logger.info('cannot compile fragment %r', pattern)
                continue
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
        """Processes the tag value and returns parsed content.

        The base implementation returns ``value`` unchanged; subclasses
        override it to build model objects (amounts, balances, dates, ...).

        Args:
            transactions: The transactions model instance.
            value: The parsed group dictionary to process.

        Returns:
            The processed mapping.
        """
        # Part of the tag protocol, the base implementation needs no context.
        del transactions
        return value

    def __new__(cls, *args: typing.Any, **kwargs: typing.Any) -> Self:
        """Create a Tag instance, deriving its ``name``, ``slug`` and logger.

        The ``slug`` is the snake_case form of the class name and is used to
        look up matching pre/post processors.

        Returns:
            The new, not yet initialised, tag instance.
        """
        # Tags take no constructor arguments, the signature only mirrors the
        # ``__init__`` of subclasses.
        del args, kwargs
        cls.name = cls.__name__
        words = re.findall(r'([A-Z][a-z]+)', cls.__name__)
        cls.slug = '_'.join(w.lower() for w in words)
        cls.logger = logger.getChild(cls.name)
        return object.__new__(cls)

    def __eq__(self, other: object) -> bool:
        """Return whether ``other`` is this very tag instance.

        Tags compare by identity, as they did in 5.0.0, so two instances of
        one class stay distinct set members and dictionary keys. The
        id-based ``__hash__`` is consistent with that: an object is always
        equal to itself.
        """
        return self is other

    def __hash__(self) -> int:
        """Return a hash based on the tag's ``id``.

        Returns:
            The integer hash of the tag.
        """
        return hash(self.id) if isinstance(self.id, str) else self.id


class DateTimeIndication(Tag):
    """Date/Time indication at which the report was created.

    Pattern: 6!n4!n1! x4!n
    """

    id: ClassVar[str | int] = 13
    pattern: ClassVar[str] = r"""^
    (?P<year>\d{2})
    (?P<month>\d{2})
    (?P<day>\d{2})
    (?P<hour>\d{2})
    (?P<minute>\d{2})
    ((?P<offset_sign>[+-])(?P<offset>\d{4}))?
    """

    def __call__(
        self, transactions: models.Transactions, value: dict[str, typing.Any]
    ) -> dict[str, object]:
        """Return the report :class:`~mt940.models.DateTime` as ``date``."""
        data = super().__call__(transactions, value)
        # Drop the raw groups so they are not passed on when the offset is
        # absent, which then yields a naive datetime.
        sign: str | None = data.pop('offset_sign', None)
        offset: str | None = data.pop('offset', None)
        if offset and _options_of(transactions).timezone_offset:
            # The subfield is a signed HHMM value: +0130 is one hour and
            # thirty minutes east of UTC, and models.DateTime wants minutes.
            minutes: int = int(offset[:2]) * 60 + int(offset[2:])
            data['offset'] = -minutes if sign == '-' else minutes
        elif offset:
            # 5.0.0 handed the digits to FixedOffset as a minute count, so
            # +0100 became 100 minutes with '0100' as the zone name.
            data['offset'] = f'-{offset}' if sign == '-' else offset
        return {'date': models.DateTime(**data)}


class TransactionReferenceNumber(Tag):
    """Transaction reference number.

    Pattern: 16x
    """

    id: ClassVar[str | int] = 20
    pattern: ClassVar[str] = r'(?P<transaction_reference>.{0,16})'


class RelatedReference(Tag):
    """Related reference.

    Pattern: 16x
    """

    id: ClassVar[str | int] = 21
    pattern: ClassVar[str] = r'(?P<related_reference>.{0,16})'


class AccountIdentification(Tag):
    """Account identification.

    Pattern: 35x
    """

    id: ClassVar[str | int] = 25
    pattern: ClassVar[str] = r'(?P<account_identification>.{0,35})'


class StatementNumber(Tag):
    """Statement number / sequence number.

    Pattern: 5n[/5n]
    """

    id: ClassVar[str | int] = 28
    pattern: ClassVar[str] = r"""
    (?P<statement_number>\d{1,5})  # 5n
    (?:/?(?P<sequence_number>\d{1,5}))?  # [/5n]
    $"""


class FloorLimitIndicator(Tag):
    """Floor limit indicator.

    Indicates the minimum value reported for debit and credit amounts.

    Pattern: :34F:GHSC0,00
    """

    id: ClassVar[str | int] = 34
    pattern: ClassVar[str] = r"""^
    (?P<currency>[A-Z]{3})  # 3!a Currency
    (?P<status>[DC ]?)  # 2a Debit/Credit Mark
    (?P<amount>[0-9,]{0,16})  # 15d Amount (includes decimal sign, so 16)
    $"""

    def __call__(
        self, transactions: models.Transactions, value: dict[str, typing.Any]
    ) -> dict[str, object]:
        """Return the floor limit as ``d_floor_limit``/``c_floor_limit``."""
        data = typing.cast(
            'dict[str, str | None]',
            super().__call__(transactions, value),
        )
        options = _options_of(transactions)
        # A missing mark counts as absent, as it did in 5.0.0.
        status: str = data.get('status') or ''
        if options.floor_limit_blank_mark:
            # A space (sent by e.g. Fiducia/Volksbank, d36c51b) means
            # "both", like an absent mark. Without the option it survives
            # into the key, as ' _floor_limit'. The sign of a lowercase mark
            # is Amount's business, through case_insensitive_marks.
            status = status.strip()
        amount: str = data.get('amount') or ''
        currency = data.get('currency')
        if status:
            key: str = status.lower() + '_floor_limit'
            return {
                key: models.Amount(amount, status, currency, options=options)
            }
        return {
            'd_floor_limit': models.Amount(
                amount, 'D', currency, options=options
            ),
            'c_floor_limit': models.Amount(
                amount, 'C', currency, options=options
            ),
        }


class NonSwift(Tag):
    """Non-swift extension for MT940 containing extra information.

    The actual definition is not consistent between banks so the current
    implementation is a tad limited. Feel free to extend the implementation
    and create a pull request with a better version :).

    It seems this could be anything so we'll have to be flexible about it.

    Pattern: `2!n35x | *x`
    """

    scope: ClassVar[type[models.Transactions | models.Transaction]] = (
        models.TransactionsAndTransaction
    )
    id: ClassVar[str | int] = 'NS'

    # NS content is bank specific and free-form, so accept anything
    # (including multi-line values whose lines do not all start with a
    # two-digit sub-tag); `__call__` extracts the `2!n35x` structure per
    # line where present.
    pattern: ClassVar[str] = r"""
    (?P<non_swift>[\s\S]*)
    $"""
    sub_pattern: ClassVar[str] = r"""
    (?P<ns_id>\d{2})(?P<ns_data>.{0,})
    """
    sub_pattern_m: ClassVar[re.Pattern[str]] = re.compile(
        sub_pattern, re.IGNORECASE | re.VERBOSE | re.UNICODE
    )

    def __call__(
        self, transactions: models.Transactions, value: dict[str, typing.Any]
    ) -> dict[str, object]:
        """Return ``value`` with per-line ``non_swift_<id>`` fields added."""
        keep_free_text = _options_of(transactions).non_swift_free_text
        text: list[str] = []
        data = value['non_swift']
        for line in data.split('\n'):
            frag = self.sub_pattern_m.match(line)
            if frag and frag.group(2):
                ns = frag.groupdict()
                value['non_swift_' + ns['ns_id']] = ns['ns_data']
                text.append(ns['ns_data'])
            elif keep_free_text and line.strip():
                # Free-form line without a two-digit sub-tag: keep the
                # content instead of dropping it.
                text.append(line.strip())
            elif text and text[-1]:
                # Blank line, or in 5.0.0 any line without a sub-tag after
                # content: collapse runs into one paragraph separator.
                text.append('')
            elif line.strip():
                # 5.0.0 kept a free-form line only at the start of the text
                # or after a separator.
                text.append(line.strip())
        value['non_swift_text'] = '\n'.join(text)
        value['non_swift'] = data
        return value


class BalanceBase(Tag):
    """Balance base.

    Pattern: 1!a6!n3!a15d
    """

    pattern: ClassVar[str] = r"""^
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
        """Return a :class:`~mt940.models.Balance` under the tag's slug."""
        data = super().__call__(transactions, value)
        options = _options_of(transactions)
        data['amount'] = models.Amount(**data, options=options)
        data['date'] = models.Date(**data)
        return {self.slug: models.Balance(**data, options=options)}


class OpeningBalance(BalanceBase):
    """Opening balance (``:60:``)."""

    id: ClassVar[str | int] = 60


class FinalOpeningBalance(BalanceBase):
    """Final opening balance (``:60F:``)."""

    id: ClassVar[str | int] = '60F'


class IntermediateOpeningBalance(BalanceBase):
    """Intermediate opening balance (``:60M:``)."""

    id: ClassVar[str | int] = '60M'


class Statement(Tag):
    """Statement line, a single transaction on the account (``:61:``).

    Each transaction is identified by a unique transaction reference number
    (Tag 20) and is described in the Statement Line (Tag 61).

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

    id: ClassVar[str | int] = 61
    scope: ClassVar[type[models.Transactions | models.Transaction]] = (
        models.Transaction
    )
    pattern: ClassVar[str] = r"""^
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
    # Supplementary details: the SWIFT spec caps this at 34x, but some banks
    # (e.g. Wise, issue #117) send more, so the length limit is relaxed. This
    # only ever turns a previous parse error into a successful parse.
    (\n?(?P<extra_details>.*))?
    $"""

    def __call__(
        self, transactions: models.Transactions, value: dict[str, typing.Any]
    ) -> dict[str, object]:
        """Return the data with the amount and dates built."""
        data = super().__call__(transactions, value)
        data.setdefault('currency', transactions.currency)
        data['amount'] = models.Amount(
            **data, options=_options_of(transactions)
        )
        date = data['date'] = models.Date(**data)

        entry_day = str(data.get('entry_day') or '')
        entry_month = str(data.get('entry_month') or '')

        if entry_day.isdigit() and entry_month.isdigit():
            entry_date = models.Date(
                day=entry_day, month=entry_month, year=str(date.year)
            )
            if (
                date > entry_date
                and (date - entry_date).days >= _YEAR_BOUNDARY_DAYS
            ):
                year = 1
            elif (
                entry_date > date
                and (entry_date - date).days >= _YEAR_BOUNDARY_DAYS
            ):
                year = -1
            else:
                year = 0

            # Correct the entry date's year when the entry date crosses a
            # year boundary relative to the value date (issue #121). Both
            # `entry_date` and `guessed_entry_date` expose the resolved value;
            # `guessed_entry_date` is kept as a backwards-compatible alias.
            if year:
                entry_date = models.Date(
                    day=entry_date.day,
                    month=entry_date.month,
                    year=entry_date.year + year,
                )
            data['entry_date'] = entry_date
            data['guessed_entry_date'] = entry_date

        return data


class StatementASNB(Statement):
    """StatementASNB.

    From: https://www.sepaforcorporates.com/swift-for-corporates

    Pattern: 6!n[4!n]2a[1!a]15d1!a3!c34x[//16x]
    [34x]

    But ASN bank puts the IBAN in the customer reference, which is according
    to Wikipedia at most 34 characters.

    So this is the new pattern:

    Pattern: 6!n[4!n]2a[1!a]15d1!a3!c34x[//16x]
    [34x]
    """

    pattern: ClassVar[str] = r"""^
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
        """Return the statement data, built exactly like :class:`Statement`."""
        return super().__call__(transactions, value)


class StatementGLS(Statement):
    """Statement variant for GLS / Atruvia banks (issue #111).

    These banks send a customer reference longer than the SWIFT 16x cap,
    followed by the ``//`` bank-reference delimiter (e.g.
    ``...DR20,NTRFBIPI-dvT1FzfMqvzF5HaU4oetlH7SGRkonU//2022070616391534000``).

    This is an opt-in tag because relaxing the default customer-reference
    length would change how banks that legitimately pack data after a 16x
    reference (e.g. Rabobank) are parsed. Enable it explicitly::

        import mt940

        gls = mt940.tags.StatementGLS()
        mt940.parse(data, tags={gls.id: gls})
    """

    pattern: ClassVar[str] = r"""^
    (?P<year>\d{2})  # 6!n Value Date (YYMMDD)
    (?P<month>\d{2})
    (?P<day>\d{2})
    (?P<entry_month>\d{2}|\s{2})?  # [4!n] Entry Date (MMDD)
    (?P<entry_day>\d{2}|\s{2})?
    (?P<status>R?[DC])  # 2a Debit/Credit Mark
    (?P<funds_code>[A-Z])?
    [\n ]?
    (?P<amount>[\d,]{1,15})  # 15d Amount
    (?P<id>[A-Z][A-Z0-9 ]{3})?
    # Customer reference of any length, up to the // bank reference.
    (?P<customer_reference>(?:(?!//)[^\n])*)
    (//(?P<bank_reference>.{0,23}))?
    (\n?(?P<extra_details>.*))?
    $"""


class ClosingBalance(BalanceBase):
    """Closing balance (``:62:``)."""

    id: ClassVar[str | int] = 62


class IntermediateClosingBalance(ClosingBalance):
    """Intermediate closing balance (``:62M:``)."""

    id: ClassVar[str | int] = '62M'


class FinalClosingBalance(ClosingBalance):
    """Final closing balance (``:62F:``)."""

    id: ClassVar[str | int] = '62F'


class AvailableBalance(BalanceBase):
    """Available balance (``:64:``)."""

    id: ClassVar[str | int] = 64


class ForwardAvailableBalance(BalanceBase):
    """Forward available balance (``:65:``)."""

    id: ClassVar[str | int] = 65


class TransactionDetails(Tag):
    """Transaction details.

    Pattern: 6x65x
    """

    id: ClassVar[str | int] = 86
    scope: ClassVar[type[models.Transactions | models.Transaction]] = (
        models.Transaction
    )
    # The SWIFT spec caps this field at 6 lines of 65 characters, but many
    # banks send more. The capture is unbounded: the parser in
    # `models.Transactions.parse` already limits the value to this tag's own
    # slice of the statement. `parse` below applies the 5.0.0 cap of nine
    # 65-character chunks unless `Options.unbounded_details` is on.
    pattern: ClassVar[str] = r"""
    (?P<transaction_details>[\s\S]*)
    """

    def parse(
        self, transactions: models.Transactions, value: str
    ) -> dict[str, str | None]:
        """Capture the details, cut like 5.0.0 did unless opted out.

        Args:
            transactions: The collection being parsed, for its options.
            value: The raw tag value.

        Returns:
            The ``transaction_details`` group.
        """
        data = super().parse(transactions, value)
        if not _options_of(transactions).unbounded_details:
            details = data['transaction_details'] or ''
            match = _LEGACY_DETAILS_RE.match(details)
            data['transaction_details'] = match.group(0) if match else ''
        return data


class SumEntries(Tag):
    """Number and Sum of debit Entries."""

    id: ClassVar[str | int] = 90
    pattern: ClassVar[str] = r"""^
    (?P<number>\d*)
    (?P<currency>.{3})  # 3!a Currency
    (?P<amount>[\d,]{1,15})  # 15d Amount
    """
    status: ClassVar[str]

    def __call__(
        self, transactions: models.Transactions, value: dict[str, typing.Any]
    ) -> dict[str, object]:
        """Return a :class:`~mt940.models.SumAmount` under the tag's slug."""
        data = super().__call__(transactions, value)
        data['status'] = self.status
        return {
            self.slug: models.SumAmount(
                **data, options=_options_of(transactions)
            )
        }


class SumDebitEntries(SumEntries):
    """Number and sum of debit entries (``:90D:``)."""

    status: ClassVar[str] = 'D'
    id: ClassVar[str | int] = '90D'


class SumCreditEntries(SumEntries):
    """Number and sum of credit entries (``:90C:``)."""

    status: ClassVar[str] = 'C'
    id: ClassVar[str | int] = '90C'


@enum.unique
class Tags(enum.Enum):
    """Registry of the built-in tag parsers, one instance per member."""

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


#: Mapping of tag id (``int`` or ``str``) to the tag instance that parses it.
TAG_BY_ID = {t.value.id: t.value for t in Tags}
