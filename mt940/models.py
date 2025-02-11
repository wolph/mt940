from __future__ import annotations

import datetime
import decimal
import re
import typing
import warnings
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any, Callable, ClassVar, overload

import mt940

from . import processors, utils

if typing.TYPE_CHECKING:
    pass


class Model:
    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}>'


class FixedOffset(datetime.tzinfo):
    """Fixed time offset based on the Python docs
    Source: https://docs.python.org/2/library/datetime.html#tzinfo-objects

    >>> offset = FixedOffset(60)
    >>> offset.utcoffset(None).total_seconds()
    3600.0
    >>> offset.dst(None)
    datetime.timedelta(0)
    >>> offset.tzname(None)
    '60'
    """

    def __init__(self, offset: int | str = 0, name: str | None = None) -> None:
        self._name = name or str(offset)

        if not isinstance(offset, int):
            offset = int(offset)
        self._offset = datetime.timedelta(minutes=offset)

    def utcoffset(self, dt: datetime.datetime | None) -> datetime.timedelta:
        return self._offset

    def dst(self, dt: datetime.datetime | None) -> datetime.timedelta:
        return datetime.timedelta(0)

    def tzname(self, dt: datetime.datetime | None) -> str:
        return self._name


class DateTime(datetime.datetime, Model):
    """Just a regular datetime object which supports dates given as strings

    >>> DateTime(
    ...     year='2000',
    ...     month='1',
    ...     day='2',
    ...     hour='3',
    ...     minute='4',
    ...     second='5',
    ...     microsecond='6',
    ... )
    DateTime(2000, 1, 2, 3, 4, 5, 6)

    >>> DateTime(
    ...     year='123',
    ...     month='1',
    ...     day='2',
    ...     hour='3',
    ...     minute='4',
    ...     second='5',
    ...     microsecond='6',
    ... )
    DateTime(2123, 1, 2, 3, 4, 5, 6)

    >>> DateTime(2000, 1, 2, 3, 4, 5, 6)
    DateTime(2000, 1, 2, 3, 4, 5, 6)

    >>> DateTime(
    ...     year='123',
    ...     month='1',
    ...     day='2',
    ...     hour='3',
    ...     minute='4',
    ...     second='5',
    ...     microsecond='6',
    ...     tzinfo=FixedOffset('60'),
    ... )
    DateTime(2123, 1, 2, 3, 4, 5, 6, tzinfo=<mt940.models.FixedOffset ...>)

    Args:
        year (str): Year (0-100), will automatically add 2000 when needed
        month (str): Month
        day (str): Day
        hour (str): Hour
        minute (str): Minute
        second (str): Second
        microsecond (str): Microsecond
        tzinfo (tzinfo): Timezone information. Overwrites `offset`
        offset (str): Timezone offset in minutes, generates a tzinfo object
                      with the given offset if no tzinfo is available.
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> DateTime:
        if kwargs:
            tzinfo = None
            if 'tzinfo' in kwargs:
                tzinfo = kwargs.pop('tzinfo')
            elif 'offset' in kwargs:
                tzinfo = FixedOffset(kwargs.pop('offset'))

            year = int(kwargs['year'])
            month = int(kwargs['month'])
            day = int(kwargs['day'])
            hour = int(kwargs.get('hour', 0))
            minute = int(kwargs.get('minute', 0))
            second = int(kwargs.get('second', 0))
            microsecond = int(kwargs.get('microsecond', 0))

            if year < 1000:
                year += 2000

            return datetime.datetime.__new__(
                cls,
                year,
                month,
                day,
                hour,
                minute,
                second,
                microsecond,
                tzinfo=tzinfo,
            )
        else:
            return datetime.datetime.__new__(cls, *args, **kwargs)


class Date(datetime.date, Model):
    """Just a regular date object which supports dates given as strings

    >>> Date(year='2000', month='1', day='2')
    Date(2000, 1, 2)

    >>> Date(year='123', month='1', day='2')
    Date(2123, 1, 2)

    Args:
        year (str): Year (0-100), will automatically add 2000 when needed
        month (str): Month
        day (str): Day
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> Date:
        if kwargs:
            dt = DateTime(*args, **kwargs).date()
            return datetime.date.__new__(cls, dt.year, dt.month, dt.day)
        else:
            return datetime.date.__new__(cls, *args, **kwargs)


class Amount(Model):
    """Amount object containing currency and amount

    Args:
        amount (str): Amount using either a , or a . as decimal separator
        status (str): Either C or D for credit or debit respectively
        currency (str): A 3 letter currency (e.g. EUR)

    >>> Amount('123.45', 'C', 'EUR')
    <123.45 EUR>
    >>> Amount('123.45', 'D', 'EUR')
    <-123.45 EUR>
    """

    def __init__(
        self,
        amount: str,
        status: str,
        currency: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.amount = decimal.Decimal(amount.replace(',', '.'))
        self.currency = currency

        # C = credit, D = debit

        if status == 'D':
            self.amount = -self.amount

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, Amount)
            and self.amount == other.amount
            and self.currency == other.currency
        )

    def __str__(self) -> str:
        return f'{self.amount} {self.currency}'

    def __repr__(self) -> str:
        return f'<{self}>'


class SumAmount(Amount):
    def __init__(
        self,
        *args: Any,
        number: int,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.number = number

    def __repr__(self) -> str:
        return f'<{self.amount} {self.currency} in {self.number} stmts)>'


class Balance(Model):
    """Parse balance statement

    Args:
        status (str): Either C or D for credit or debit respectively
        amount (Amount | str | None): Object containing the amount and currency
            or amount string
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
    """

    def __init__(
        self,
        status: str | None = None,
        amount: Amount | str | None = None,
        date: Date | None = None,
        **kwargs: Any,
    ) -> None:
        if amount and not isinstance(amount, Amount):
            if status is None:  # pragma: no cover
                raise ValueError('Cannot create Amount without status')
            amount = Amount(amount, status, kwargs.get('currency'))
        self.status = status
        self.amount = amount
        self.date = date

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, Balance)
            and self.amount == other.amount
            and self.status == other.status
        )

    def __repr__(self) -> str:
        return f'<{self}>'

    def __str__(self) -> str:
        return f'{self.amount} @ {self.date}'


class Transaction(Model):
    def __init__(
        self,
        transactions: Transactions,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.transactions = transactions
        self.data: dict[str, Any] = {}
        self.update(data)

    def update(
        self,
        data: dict[str, Any] | None,
    ) -> None:
        """Update transaction data with provided data dictionary.

        Args:
            data (dict[str, Any] | None): Data to update the transaction with.
        """
        if data:
            self.data.update(data)

    def __repr__(self) -> str:
        return '<{}[{}] {}>'.format(
            self.__class__.__name__,
            self.data.get('date'),
            self.data.get('amount'),
        )


class Transactions(Sequence[Transaction]):
    """
    Collection of Transaction objects with global properties such
    as begin and end balance
    """

    DEFAULT_PROCESSORS: ClassVar[dict[str, list[Callable[..., Any]]]] = dict(
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
        post_statement=[
            processors.date_cleanup_post_processor,
            processors.transactions_to_transaction('transaction_reference'),
        ],
        pre_statement_number=[],
        post_statement_number=[],
        pre_non_swift=[],
        post_non_swift=[],
        pre_transaction_details=[],
        post_transaction_details=[
            processors.transaction_details_post_processor,
            # processors.transaction_details_post_processor_with_space
        ],
        pre_transaction_reference_number=[],
        post_transaction_reference_number=[],
        pre_floor_limit_indicator=[],
        post_floor_limit_indicator=[],
        pre_date_time_indication=[],
        post_date_time_indication=[],
        pre_sum_credit_entries=[],
        post_sum_credit_entries=[],
        pre_sum_debit_entries=[],
        post_sum_debit_entries=[],
    )

    def __getstate__(self) -> dict[str, Any]:
        # Processors are not always safe to dump so ignore them entirely
        state = self.__dict__.copy()
        del state['processors']
        return state

    def __init__(
        self,
        processors: dict[str, list[Callable[..., Any]]] | None = None,
        tags: dict[int | str, mt940.tags.Tag] | None = None,
    ) -> None:
        self.processors: dict[str, list[Callable[..., Any]]] = (
            self.DEFAULT_PROCESSORS.copy()
        )
        self.tags: MutableMapping[int | str, mt940.tags.Tag] = dict(
            self.default_tags()
        )

        if processors:
            self.processors.update(processors)
        if tags:
            self.tags.update(tags)

        self.transactions: list[Transaction] = []
        self.data: dict[str, Any] = {}

    @property
    def currency(self) -> str | None:
        balance = utils.coalesce(
            self.data.get('final_opening_balance'),
            self.data.get('opening_balance'),
            self.data.get('intermediate_opening_balance'),
            self.data.get('available_balance'),
            self.data.get('forward_available_balance'),
            self.data.get('final_closing_balance'),
            self.data.get('closing_balance'),
            self.data.get('intermediate_closing_balance'),
            self.data.get('c_floor_limit'),
            self.data.get('d_floor_limit'),
        )

        if balance is not None:
            if hasattr(balance, 'currency'):  # type: ignore[unreachable]
                return balance.currency

            return balance.amount.currency
        return None

    @classmethod
    def defaultTags(cls) -> Mapping[int | str, mt940.tags.Tag]:  # noqa: N802 # pragma: no cover
        warnings.warn(
            'defaultTags is deprecated, use default_tags instead',
            DeprecationWarning,
            stacklevel=2,
        )
        return cls.default_tags()

    @staticmethod
    def default_tags() -> Mapping[int | str, mt940.tags.Tag]:
        return mt940.tags.TAG_BY_ID

    def parse(self, data: str) -> list[Transaction]:
        """Parses mt940 data, expects a string with data

        Args:
            data (str): The MT940 data

        Returns:
            list[Transaction]: list of Transaction
        """
        # Remove extraneous whitespace and such
        data = '\n'.join(self.strip(data.split('\n')))

        # The pattern is a bit annoying to match by regex, even with a greedy
        # match it's difficult to get both the beginning and the end so we're
        # working around it in a safer way to get everything.
        tag_re = re.compile(
            r'^:\n?(?P<full_tag>(?P<tag>[0-9]{2}|NS)(?P<sub_tag>[A-Z])?):',
            re.MULTILINE,
        )
        matches = list(tag_re.finditer(data))

        # identify valid matches
        valid_matches = self.sanitize_tag_id_matches(matches)

        for i, match in enumerate(valid_matches):
            self._process_match(match, i, valid_matches, data)

        return self.transactions

    def _process_match(
        self,
        match: re.Match[str],
        i: int,
        valid_matches: list[re.Match[str]],
        data: str,
    ) -> None:
        tag_id = self.normalize_tag_id(match.group('tag'))

        # get tag instance corresponding to tag id
        tag = self.tags.get(match.group('full_tag')) or self.tags[tag_id]

        # Nice trick to get all the text that is part of this tag, python
        # regex matches have a `end()` and `start()` to indicate the start
        # and end index of the match.

        if valid_matches[i + 1 : i + 2]:
            tag_data = data[match.end() : valid_matches[i + 1].start()].strip()
        else:
            tag_data = data[match.end() :].strip()

        tag_dict: dict[str, Any] = tag.parse(self, tag_data)

        # Preprocess data before creating the object

        for processor in self.processors.get(f'pre_{tag.slug}', []):
            tag_dict = processor(self, tag, tag_dict)

        result: Any = tag(self, tag_dict)

        # Postprocess the object

        for processor in self.processors.get(f'post_{tag.slug}', []):
            result = processor(self, tag, tag_dict, result)

        if isinstance(tag, mt940.tags.Statement):
            self._process_statement_tag(result)
        elif issubclass(tag.scope, Transaction) and self.transactions:
            self._update_transaction(result)
        elif issubclass(  # pragma: no branch
            tag.scope, Transactions
        ):  # pyright: ignore [reportUnnecessaryIsInstance]
            self.data.update(result)

    def _process_statement_tag(self, result: dict[str, Any]) -> None:
        if not self.transactions:
            transaction = Transaction(self)
            self.transactions.append(transaction)

        transaction = self.transactions[-1]
        if transaction.data.get('id'):
            transaction = Transaction(self, result)
            self.transactions.append(transaction)
        else:
            transaction.data.update(result)

    def _update_transaction(self, result: dict[str, Any]) -> None:
        transaction = self.transactions[-1]
        for k, v in result.items():
            if k in transaction.data and hasattr(v, 'strip'):
                if transaction.data[k] is None:
                    transaction.data[k] = v.strip()
                else:
                    transaction.data[k] += '\n%s' % v.strip()
            else:
                transaction.data[k] = v

    @overload
    def __getitem__(self, key: int) -> Transaction: ...

    @overload
    def __getitem__(self, key: slice) -> list[Transaction]: ...

    def __getitem__(
        self,
        key: int | slice,
    ) -> Transaction | list[Transaction]:
        return self.transactions[key]

    def __len__(self) -> int:
        return len(self.transactions)

    def __repr__(self) -> str:
        return '<{}[{}]>'.format(
            self.__class__.__name__,
            ']['.join(
                '{}: {}'.format(k.replace('_balance', ''), v)
                for k, v in self.data.items()
                if k.endswith('balance')
            ),
        )

    @staticmethod
    def strip(lines: list[str]) -> list[str]:
        """Strip extraneous whitespace and lines from list of strings.

        Args:
            lines (list[str]): List of lines to strip.

        Returns:
            list[str]: List of cleaned lines.
        """
        stripped_lines: list[str] = []
        for line in lines:
            line = line.replace('\r', '')
            line = line.rstrip()
            if line.strip() == '-':
                continue
            if line:
                stripped_lines.append(line)
        return stripped_lines

    @classmethod
    def normalize_tag_id(cls, tag_id: str) -> int | str:
        """Normalize a tag ID to int if possible, or return as string.

        Args:
            tag_id (str): The tag ID to normalize.

        Returns:
            int | str: Normalized tag ID as integer or string.
        """
        if tag_id.isdigit():
            return int(tag_id)
        return tag_id

    def sanitize_tag_id_matches(
        self,
        matches: list[re.Match[str]],
    ) -> list[re.Match[str]]:
        """Sanitize the list of tag ID matches.

        Args:
            matches (list[re.Match[str]]):
                List of regex match objects for tag IDs.

        Returns:
            list[re.Match[str]]:
                List of valid match objects for recognized tag IDs.
        """
        i_next = 0
        valid_matches: list[re.Match[str]] = []
        for i, match in enumerate(matches):
            if i < i_next:
                continue
            i_next = i + 1
            tag_id = self.normalize_tag_id(match.group('tag'))
            if tag_id not in self.tags:  # pragma: no cover
                continue

            if tag_id == mt940.tags.Tags.TRANSACTION_DETAILS.value.id:
                for j in range(i_next, len(matches)):
                    next_tag_id = self.normalize_tag_id(
                        matches[j].group('tag'),
                    )
                    if next_tag_id in self.tags:
                        i_next = j
                        break
            valid_matches.append(match)
        return valid_matches


class TransactionsAndTransaction(Transactions, Transaction):  # type: ignore[misc]
    """
    Subclass of both Transactions and Transaction for scope definitions.

    This is useful for the non-swift data for example which can function both
    as details for a transaction and for a collection of transactions.
    """
