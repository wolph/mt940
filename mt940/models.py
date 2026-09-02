"""Data models returned by the MT940 parser.

The parser produces a :class:`Transactions` collection (statement-level data
plus a sequence of :class:`Transaction` objects). The remaining classes are the
value types stored on them: :class:`Amount`, :class:`Balance`, :class:`Date`,
:class:`DateTime` and :class:`FixedOffset`. They accept the string fields
found in raw MT940 data and coerce them to native Python types.
"""

from __future__ import annotations

import datetime
import decimal
import re
import warnings
from collections.abc import (
    Iterable,
    Mapping,
    MutableMapping,
    Sequence,
)
from typing import TYPE_CHECKING, Any, ClassVar, overload

import mt940

from . import processors, utils

# Kept at runtime: 5.0.0 exposed it as mt940.models.Processors.
from ._types import Processors as Processors  # noqa: PLC0414, TC001
from .options import Options

if TYPE_CHECKING:
    from typing_extensions import Self

#: Sentinel for attributes that are absent, as opposed to ``None``.
_MISSING = object()


#: MT940 carries two-digit years. Anything below this limit is taken to be
#: relative to :data:`_SHORT_YEAR_BASE`, so ``23`` becomes ``2023``.
_SHORT_YEAR_LIMIT = 1000
_SHORT_YEAR_BASE = 2000


class Model:
    """Base class for MT940 models, providing a uniform ``repr``."""

    def __repr__(self) -> str:
        """Return the class name in angle brackets."""
        return f'<{self.__class__.__name__}>'


class FixedOffset(datetime.tzinfo):
    """Fixed time offset, after the ``tzinfo`` example in the Python docs.

    Source: https://docs.python.org/3/library/datetime.html#tzinfo-objects

    >>> offset = FixedOffset(60)
    >>> offset.utcoffset(None).total_seconds()
    3600.0
    >>> offset.dst(None)
    datetime.timedelta(0)
    >>> offset.tzname(None)
    '60'
    """

    def __init__(self, offset: int | str = 0, name: str | None = None) -> None:
        """Store the offset in minutes east of UTC and an optional name.

        Args:
            offset: Minutes east of UTC, as an ``int`` or a numeric string.
            name: The zone name, defaults to the offset as a string.
        """
        self._name: str = name or str(offset)

        if not isinstance(offset, int):
            offset = int(offset)
        self._offset: datetime.timedelta = datetime.timedelta(minutes=offset)

    def utcoffset(self, dt: datetime.datetime | None) -> datetime.timedelta:
        """Return the fixed offset east of UTC."""
        del dt
        return self._offset

    def dst(  # noqa: PLR6301 (the tzinfo API is instance-based)
        self, dt: datetime.datetime | None
    ) -> datetime.timedelta:
        """Return a zero DST adjustment (fixed offsets have no DST)."""
        del dt
        return datetime.timedelta(0)

    def tzname(self, dt: datetime.datetime | None) -> str:
        """Return the offset's name."""
        del dt
        return self._name


class DateTime(datetime.datetime, Model):
    """Just a regular datetime object which supports dates given as strings.

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
        tzinfo (datetime.tzinfo): Timezone information. Overwrites `offset`
        offset (str): Timezone offset in minutes, generates a tzinfo object
                      with the given offset if no tzinfo is available.
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        """Build a ``DateTime`` from string or positional date components.

        When keyword arguments are given the individual fields are coerced from
        strings, two-digit years are shifted into the 2000s, and ``offset`` (in
        minutes) is converted to a :class:`FixedOffset`. Positional arguments
        fall through to :class:`datetime.datetime`.
        """
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

            if year < _SHORT_YEAR_LIMIT:
                year += _SHORT_YEAR_BASE

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
        return datetime.datetime.__new__(cls, *args, **kwargs)


class Date(datetime.date, Model):
    """Just a regular date object which supports dates given as strings.

    >>> Date(year='2000', month='1', day='2')
    Date(2000, 1, 2)

    >>> Date(year='123', month='1', day='2')
    Date(2123, 1, 2)

    Args:
        year (str): Year (0-100), will automatically add 2000 when needed
        month (str): Month
        day (str): Day
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        """Build a ``Date`` from string or positional date components.

        Keyword arguments are coerced through :class:`DateTime` (so two-digit
        years are normalised); positional arguments fall through to
        :class:`datetime.date`.
        """
        if kwargs:
            dt = DateTime(*args, **kwargs).date()
            return datetime.date.__new__(cls, dt.year, dt.month, dt.day)
        return datetime.date.__new__(cls, *args, **kwargs)


class Amount(Model):
    """Amount object containing currency and amount.

    Args:
        amount (str): Amount using either a , or a . as decimal separator
        status (str): The debit/credit mark of field 61, one of C, D, RC or
            RD. C and RD are positive, D and RC are negative.
        currency (str): A 3 letter currency (e.g. EUR)

    >>> Amount('123.45', 'C', 'EUR')
    <123.45 EUR>
    >>> Amount('123.45', 'D', 'EUR')
    <-123.45 EUR>

    Release 5.0.0 negated a plain ``D`` only, so a reversal of a credit
    (``RC``) and a lowercase ``d`` came back positive. That stays the
    default. Opt in through :class:`mt940.options.Options` to sign them:

    >>> Amount('123.45', 'RC', 'EUR')
    <123.45 EUR>
    >>> Amount(
    ...     '123.45', 'RC', 'EUR', options=mt940.Options(reversal_sign=True)
    ... )
    <-123.45 EUR>
    >>> Amount(
    ...     '1.00',
    ...     'd',
    ...     'EUR',
    ...     options=mt940.Options(case_insensitive_marks=True),
    ... )
    <-1.00 EUR>

    A reversal of a debit puts money back in, so it stays positive:

    >>> Amount('123.45', 'RD', 'EUR', options=mt940.Options.all())
    <123.45 EUR>
    """

    def __init__(
        self,
        amount: str,
        status: str | None,
        currency: str | None = None,
        *,
        options: Options | None = None,
        **kwargs: Any,
    ) -> None:
        """Coerce ``amount`` to a signed :class:`decimal.Decimal`.

        Args:
            amount: The amount, with ``,`` or ``.`` as decimal separator.
            status: The debit/credit mark of field 61. ``None`` counts as
                no mark.
            currency: The three-letter currency code.
            options: Which marks negate the amount, see
                :class:`mt940.options.Options`. By default only a plain
                ``D`` does, like release 5.0.0.
            **kwargs: Ignored, so a parsed tag dictionary can be splatted
                in directly.
        """
        del kwargs
        self.amount: decimal.Decimal = decimal.Decimal(
            amount.replace(',', '.')
        )
        self.currency: str | None = currency

        # C = credit, D = debit, RC = reversal of a credit (money leaves the
        # account, like a debit), RD = reversal of a debit (money comes back
        # in, like a credit). The tag patterns compile with re.IGNORECASE,
        # so a lowercase mark reaches this constructor as-is.
        options = options or Options()
        mark = status or ''
        if options.case_insensitive_marks:
            mark = mark.upper()
        debit_marks = {'D', 'RC'} if options.reversal_sign else {'D'}
        if mark in debit_marks:
            self.amount = -self.amount

    def __eq__(self, other: object) -> bool:
        """Return whether ``other`` is an equal-valued ``Amount``."""
        return (
            isinstance(other, Amount)
            and self.amount == other.amount
            and self.currency == other.currency
        )

    def __hash__(self) -> int:
        """Return a hash of amount and currency, matching ``__eq__``."""
        return hash((self.amount, self.currency))

    def __str__(self) -> str:
        """Return ``'<amount> <currency>'``."""
        return f'{self.amount} {self.currency}'

    def __repr__(self) -> str:
        """Return the string form in angle brackets."""
        return f'<{self}>'


class SumAmount(Amount):
    """An :class:`Amount` that also tracks how many entries it sums.

    Used for the ``:90D:``/``:90C:`` tags, which report the total amount *and*
    the ``number`` of debit/credit entries that make it up.
    """

    def __init__(
        self,
        *args: Any,
        number: int,
        **kwargs: Any,
    ) -> None:
        """Store the entry ``number`` alongside the summed amount."""
        super().__init__(*args, **kwargs)
        self.number: int = number

    def __eq__(self, other: object) -> bool:
        """Return whether ``other`` is an equal-valued amount.

        ``number`` is informational and takes no part, as in 5.0.0: a plain
        :class:`Amount` of the same value compares equal, and so do two
        totals over a different number of entries.
        """
        return super().__eq__(other)

    def __hash__(self) -> int:
        """Return the :class:`Amount` hash, matching ``__eq__``."""
        return super().__hash__()

    def __repr__(self) -> str:
        """Return the amount, currency and entry count in angle brackets."""
        return f'<{self.amount} {self.currency} in {self.number} stmts)>'


class Balance(Model):
    """Parse balance statement.

    Args:
        status (str): Either C or D for credit or debit respectively
        amount (Amount | str | None): Object containing the amount and currency
            or amount string
        date (Date | None): The balance date

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
        *,
        options: Options | None = None,
        **kwargs: Any,
    ) -> None:
        """Store the balance, coercing a string ``amount`` to an ``Amount``.

        An empty amount string is stored as it is, like release 5.0.0 did.

        Args:
            status: The debit/credit mark, needed to sign a string amount.
            amount: An :class:`Amount`, or an amount string to coerce.
            date: The balance date.
            options: Passed on to :class:`Amount` when coercing.
            **kwargs: Extra parsed tag fields, only ``currency`` is used.

        Raises:
            ValueError: When ``amount`` is a non-empty string and ``status``
                is missing.
        """
        if isinstance(amount, str) and amount:
            if status is None:
                msg = 'Cannot create Amount without status'
                raise ValueError(msg)
            amount = Amount(
                amount, status, kwargs.get('currency'), options=options
            )
        self.status: str | None = status
        self.amount: Amount | str | None = amount
        self.date: Date | None = date

    def __eq__(self, other: object) -> bool:
        """Return whether ``other`` is an equal-valued ``Balance``."""
        return (
            isinstance(other, Balance)
            and self.amount == other.amount
            and self.status == other.status
        )

    def __hash__(self) -> int:
        """Return a hash of amount and status, matching ``__eq__``."""
        return hash((self.amount, self.status))

    def __repr__(self) -> str:
        """Return the string form in angle brackets."""
        return f'<{self}>'

    def __str__(self) -> str:
        """Return ``'<amount> @ <date>'``."""
        return f'{self.amount} @ {self.date}'


class Transaction(Model):
    """A single statement transaction and its parsed fields.

    Holds a back-reference to its owning :class:`Transactions` collection and a
    ``data`` dictionary with the parsed tag fields (amount, dates, references,
    purpose, ...). Field availability depends on the source bank and tags.
    """

    def __init__(
        self,
        transactions: Transactions,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Create a transaction owned by ``transactions``.

        Args:
            transactions: The collection this transaction belongs to.
            data: Optional initial field data to populate.
        """
        self.transactions: Transactions = transactions
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
        """Return the class name with the transaction date and amount."""
        return '<{}[{}] {}>'.format(
            self.__class__.__name__,
            self.data.get('date'),
            self.data.get('amount'),
        )


class Transactions(Sequence[Transaction]):
    """Collection of Transaction objects with statement-level properties.

    The statement-level data, such as the opening and closing balances, lives
    in ``data``, the transactions themselves in ``transactions``.
    """

    DEFAULT_PROCESSORS: ClassVar[Processors] = {
        'pre_account_identification': [],
        'post_account_identification': [],
        'pre_available_balance': [],
        'post_available_balance': [],
        'pre_closing_balance': [],
        'post_closing_balance': [],
        'pre_intermediate_closing_balance': [],
        'post_intermediate_closing_balance': [],
        'pre_final_closing_balance': [],
        'post_final_closing_balance': [],
        'pre_forward_available_balance': [],
        'post_forward_available_balance': [],
        'pre_opening_balance': [],
        'post_opening_balance': [],
        'pre_intermediate_opening_balance': [],
        'post_intermediate_opening_balance': [],
        'pre_final_opening_balance': [],
        'post_final_opening_balance': [],
        'pre_related_reference': [],
        'post_related_reference': [],
        'pre_statement': [processors.date_fixup_pre_processor],
        'post_statement': [
            processors.date_cleanup_post_processor,
            processors.transactions_to_transaction('transaction_reference'),
        ],
        'pre_statement_number': [],
        'post_statement_number': [],
        'pre_non_swift': [],
        'post_non_swift': [],
        'pre_transaction_details': [],
        'post_transaction_details': [
            processors.transaction_details_post_processor,
            # processors.transaction_details_post_processor_with_space
        ],
        'pre_transaction_reference_number': [],
        'post_transaction_reference_number': [],
        'pre_floor_limit_indicator': [],
        'post_floor_limit_indicator': [],
        'pre_date_time_indication': [],
        'post_date_time_indication': [],
        'pre_sum_credit_entries': [],
        'post_sum_credit_entries': [],
        'pre_sum_debit_entries': [],
        'post_sum_debit_entries': [],
    }

    def __getstate__(self) -> dict[str, Any]:
        """Return picklable state, dropping the (unpicklable) processors."""
        # Processors are not always safe to dump so ignore them entirely
        state = self.__dict__.copy()
        del state['processors']
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore unpickled state, re-creating the dropped processors.

        ``__getstate__`` omits :attr:`processors`, so it is rebuilt from
        :attr:`DEFAULT_PROCESSORS` here to keep the unpickled object usable.
        """
        self.__dict__.update(state)
        self.processors: Processors = self.DEFAULT_PROCESSORS.copy()
        # Pickles written by 5.0.0 predate the options attribute.
        _ = self.__dict__.setdefault('options', Options())

    def __init__(
        self,
        processors: Processors | None = None,
        tags: dict[int | str, mt940.tags.Tag] | None = None,
        transaction_boundary: Iterable[str] | None = None,
        *,
        options: Options | None = None,
    ) -> None:
        """Create an empty collection, optionally customizing parsing.

        Args:
            processors: Extra pre/post processors merged over
                :attr:`DEFAULT_PROCESSORS`.
            tags: Extra or overriding tag parsers merged over the defaults.
            transaction_boundary: Tag *slugs* that each open a new transaction
                (issue #110). By default only ``:61:`` starts one; a bare
                string is treated as a single slug. Omit to keep the legacy
                behaviour.
            options: Opt-in behaviours, see :class:`mt940.options.Options`.
                Omit to parse exactly like release 5.0.0.
        """
        self.options: Options = options or Options()
        self.processors = self.DEFAULT_PROCESSORS.copy()
        self.tags: MutableMapping[int | str, mt940.tags.Tag] = dict(
            self.default_tags()
        )

        if processors:
            self.processors.update(processors)
        if tags:
            self.tags.update(tags)

        # Opt-in (issue #110): tag slugs that each open a new transaction.
        # Banks differ in how they delimit transactions; by default only the
        # `:61:` statement tag starts a transaction. Passing e.g.
        # ``{'transaction_reference_number'}`` makes each `:20:` start its own
        # transaction too. Empty (the default) preserves the legacy behaviour.
        if isinstance(transaction_boundary, str):
            # A bare string is almost certainly a single slug, not an iterable
            # of single characters.
            transaction_boundary = (transaction_boundary,)
        self.transaction_boundary: frozenset[str] = frozenset(
            transaction_boundary or ()
        )

        self.transactions: list[Transaction] = []
        self.data: dict[str, Any] = {}

    @property
    def currency(self) -> str | None:
        """The statement currency, derived from the first available balance.

        Returns ``None`` when no balance or floor-limit carrying a currency has
        been parsed yet.
        """
        balance: object = utils.coalesce(
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

        if balance is None:
            return None
        # Floor limits are bare amounts, balances wrap one. Duck-typed, as
        # in 5.0.0: anything with a currency, or with an amount that has one,
        # counts. Nothing usable gives None instead of an error.
        currency: object = getattr(balance, 'currency', _MISSING)
        if currency is _MISSING:
            amount: object = getattr(balance, 'amount', None)
            currency = getattr(amount, 'currency', None)
        return currency if isinstance(currency, str) else None

    @classmethod
    def defaultTags(cls) -> Mapping[int | str, mt940.tags.Tag]:  # noqa: N802
        """Return :meth:`default_tags`, with a deprecation warning.

        Returns:
            The built-in tag parsers keyed by tag id.
        """
        warnings.warn(
            'defaultTags is deprecated, use default_tags instead',
            DeprecationWarning,
            stacklevel=2,
        )
        return cls.default_tags()

    @staticmethod
    def default_tags() -> Mapping[int | str, mt940.tags.Tag]:
        """Return the built-in tag parsers keyed by tag id."""
        return mt940.tags.TAG_BY_ID

    def parse(self, data: str) -> list[Transaction]:
        """Parses mt940 data, expects a string with data.

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
        """Parse one matched tag and route its result to the right place.

        Runs the tag's pre-processors, builds the model object, runs the
        post-processors, then files the result as either statement-level data,
        a new transaction (``:61:`` or a configured boundary tag), or an update
        to the current transaction, based on the tag's
        :attr:`~mt940.tags.Tag.scope`.
        """
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
            # Statement (:61:) handling always takes precedence so it cannot
            # be bypassed by listing its slug in transaction_boundary.
            self._process_statement_tag(result)
        elif tag.slug in self.transaction_boundary:
            # Opt-in (issue #110): this tag opens a new transaction block.
            self.transactions.append(Transaction(self, result))
            if issubclass(tag.scope, Transactions):
                # Keep statement-level data (e.g. the :20: reference) global
                # too, so later :61: tags in the same block can copy it.
                self.data.update(result)
        elif issubclass(tag.scope, Transaction) and self.transactions:
            self._update_transaction(result)
        elif issubclass(tag.scope, Transactions):
            self.data.update(result)
        # Transaction-scoped data before the first transaction has nowhere to
        # go and is dropped (the empty_86 fixture depends on this).

    def _process_statement_tag(self, result: dict[str, Any]) -> None:
        """File a ``:61:`` statement result into the current/new transaction.

        Reuses the trailing placeholder transaction if it has no ``id`` yet,
        otherwise starts a new :class:`Transaction`.
        """
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
        """Merge a transaction-scoped result into the current transaction.

        New keys are set directly. When both the existing and the incoming
        values are strings, the incoming one is appended on a new line, as
        with a multi-line ``:86:``. A structured ``:86:`` emits ``None`` for
        every sub-field it does not carry. By default such a ``None``
        replaces whatever another tag provided, as in 5.0.0, so the ``:61:``
        customer reference is lost to a later ``:86:`` without a ``KREF``.
        With :attr:`~mt940.options.Options.merge_keeps_values` a ``None``
        never replaces an existing value. Either way a later string replaces
        an existing ``None`` instead of crashing on ``None += str``.
        """
        transaction = self.transactions[-1]
        keep_values = self.options.merge_keeps_values
        for k, v in result.items():
            existing = transaction.data.get(k)
            if hasattr(existing, 'strip') and hasattr(v, 'strip'):
                transaction.data[k] += f'\n{v.strip()}'
            elif v is None and keep_values and k in transaction.data:
                continue
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
        """Return the transaction at ``key``, or a slice of them."""
        return self.transactions[key]

    def __len__(self) -> int:
        """Return the number of transactions."""
        return len(self.transactions)

    def __repr__(self) -> str:
        """Return the class name and every balance in ``data``."""
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
        for raw_line in lines:
            line = raw_line.replace('\r', '').rstrip()
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
            if tag_id not in self.tags:
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


class TransactionsAndTransaction(  # type: ignore[misc]  # pyright: ignore[reportUnsafeMultipleInheritance, reportIncompatibleVariableOverride]
    Transactions, Transaction
):
    """Scope marker for tags whose data belongs to statement and transaction.

    ``:NS:`` is the example: its content is filed both as statement data and
    as details of the current transaction. The class exists so that the
    ``issubclass`` checks against :attr:`~mt940.tags.Tag.scope` succeed for
    both bases. The parser never creates an instance, but building one works
    and behaves like an empty :class:`Transactions`, as in 5.0.0.
    """
