"""Data models returned by the MT940 parser.

The parser produces a :class:`Transactions` collection (statement-level data
plus a sequence of :class:`Transaction` objects). The remaining classes are the
value types stored on them: :class:`Amount`, :class:`Balance`, :class:`Date`,
:class:`DateTime` and :class:`FixedOffset`. They accept the string fields found
in raw MT940 data and coerce them to native Python types.
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


#: Keyword date construction adds :data:`mt940.models._SHORT_YEAR_BASE`
#: to every year below this limit, including three-digit years.
_SHORT_YEAR_LIMIT = 1000
#: Year offset added by keyword date construction below _SHORT_YEAR_LIMIT.
_SHORT_YEAR_BASE = 2000


class Model:
    """Base class for MT940 models, providing a uniform ``repr``."""

    def __repr__(self) -> str:
        """Return the class name in angle brackets."""
        return f'<{self.__class__.__name__}>'


class FixedOffset(datetime.tzinfo):
    """A timezone with a constant offset measured in minutes east of UTC.

    No daylight-saving rules are applied. The name is display metadata and need
    not identify an IANA timezone. Offset range validation is delegated to the
    ``datetime`` operations that consume this object.

    Attributes:
        _name: Supplied non-empty name, or the original offset converted to
            text.
        _offset: Offset stored as a :class:`datetime.timedelta`.

    Examples:
        >>> offset = FixedOffset(60)
        >>> offset.utcoffset(None).total_seconds()
        3600.0
        >>> offset.dst(None)
        datetime.timedelta(0)
        >>> offset.tzname(None)
        '60'
    """

    def __init__(self, offset: int | str = 0, name: str | None = None) -> None:
        """Store an offset in minutes and its display name.

        Args:
            offset: Minutes east of UTC, converted with ``int`` if not already
                an integer. Negative values represent time west of UTC.
            name: Zone name. ``None`` or an empty string uses ``str(offset)``
                before numeric conversion, so a string's leading zeroes
                survive.

        Raises:
            ValueError: A string offset is not an integer.
            OverflowError: The offset is too large for ``datetime.timedelta``.
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
    """A ``datetime`` subclass accepting string components as keywords.

    With keyword arguments, ``year``, ``month`` and ``day`` are required. Time
    components default to zero and are converted with ``int``. Any year below
    1000 has 2000 added, including three-digit years. This historical rule is
    broader than the two-digit years used by MT940.

    ``tzinfo`` takes precedence over ``offset``, even when ``tzinfo=None``.
    ``offset`` is measured in minutes and creates :class:`FixedOffset`.
    Positional arguments without keywords are passed directly to
    ``datetime.datetime``, which also preserves its binary reconstruction path
    used by pickle.

    Examples:
        >>> DateTime(year='23', month='1', day='2', hour='3', offset='60')
        DateTime(2023, 1, 2, 3, 0, tzinfo=<mt940.models.FixedOffset ...>)
        >>> DateTime(year='123', month='1', day='2')
        DateTime(2123, 1, 2, 0, 0)
        >>> DateTime(2000, 1, 2, 3, 4, 5, 6)
        DateTime(2000, 1, 2, 3, 4, 5, 6)
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        """Construct a datetime through its positional or keyword path.

        Args:
            *args: Native ``datetime.datetime`` arguments when no keywords are
                supplied. Ignored by the component-building keyword path.
            **kwargs: Required ``year``, ``month`` and ``day``, optional
                ``hour``, ``minute``, ``second``, ``microsecond``, ``tzinfo``
                and ``offset``. Extra keys are ignored so parsed tag mappings
                can be expanded directly. Native-only keywords such as ``fold``
                are not forwarded.

        Returns:
            A new instance of the called class with validated date components.

        Raises:
            KeyError: A required keyword component is absent.
            ValueError: Numeric conversion fails or a date component is out of
                range.
            TypeError: A component or timezone has an unsupported type.
            OverflowError: Numeric components exceed the native supported
                range.
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
    """A ``date`` subclass accepting string components as keywords.

    The keyword path constructs a :class:`DateTime` and keeps its calendar
    date. Years below 1000 have 2000 added. Positional arguments without
    keywords go directly to ``datetime.date``, including the binary form used
    by pickle.

    Examples:
        >>> Date(year='23', month='1', day='2')
        Date(2023, 1, 2)
        >>> Date(year='123', month='1', day='2')
        Date(2123, 1, 2)
        >>> Date(1999, 12, 31)
        Date(1999, 12, 31)
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        """Construct a date using native arguments or converted keywords.

        Args:
            *args: Native ``datetime.date`` arguments if no keywords are
                present.
            **kwargs: Components accepted by :class:`DateTime`. ``year``,
                ``month`` and ``day`` are required. Time fields are validated
                then discarded.

        Returns:
            A new date instance of the called class.

        Raises:
            KeyError: A required keyword date component is absent.
            ValueError: Numeric conversion fails or a component is out of
                range.
            TypeError: A native argument or component has an unsupported type.
            OverflowError: A component exceeds the native supported range.
        """
        if kwargs:
            dt = DateTime(*args, **kwargs).date()
            return datetime.date.__new__(cls, dt.year, dt.month, dt.day)
        return datetime.date.__new__(cls, *args, **kwargs)


class Amount(Model):
    """A decimal amount paired with an optional currency code.

    By default only the exact status ``D`` negates the supplied numeric value.
    ``Options.reversal_sign`` also negates ``RC``. Lowercase marks are
    recognised only with ``Options.case_insensitive_marks``. ``C`` and ``RD``
    leave the value unchanged. Status and currency codes are not validated or
    stored together.

    Equality and hashing use both amount and currency, including across
    ``Amount`` subclasses. Both attributes remain writable for compatibility.
    Do not change them while the object is a dictionary key or set member.

    Attributes:
        amount: Signed :class:`decimal.Decimal`. Parsing retains the input
            digits, but negation uses the active decimal context and can round
            the result.
        currency: Supplied currency string or ``None``. No conversion is
            applied.

    Examples:
        >>> Amount('123,45', 'D', 'EUR')
        <-123.45 EUR>
        >>> Amount('123.45', 'RC', 'EUR')
        <123.45 EUR>
        >>> Amount(
        ...     '123.45',
        ...     'RC',
        ...     'EUR',
        ...     options=mt940.Options(reversal_sign=True),
        ... )
        <-123.45 EUR>
        >>> Amount(
        ...     '1.00',
        ...     'd',
        ...     'EUR',
        ...     options=mt940.Options(case_insensitive_marks=True),
        ... )
        <-1.00 EUR>
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
        """Convert an amount string to a decimal and apply its status mark.

        Args:
            amount: Decimal text using a comma or point as the decimal
                separator. Conversion does not impose a scale or round to
                currency units.
            status: Debit or credit mark. ``None`` and unrecognised marks leave
                the numeric value unchanged. Negation changes an already
                negative input to positive when a debit mark applies.
            currency: Currency identifier stored without validation, or
                ``None``.
            options: Switches controlling reversal and lowercase mark handling.
                Omitting them recognises only the exact ``D`` as negative.
            **kwargs: Ignored parsed fields, allowing a whole tag mapping here.

        Raises:
            decimal.InvalidOperation: The amount is not valid decimal text
                under the active decimal context.

        Decimal arithmetic, including negation, uses the current decimal
        context.
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
    """An amount with an informational count of contributing entries.

    The debit and credit summary tags use this class. ``number`` is stored
    unchanged. Direct callers normally supply an integer, while built-in tag
    parsers supply the captured string, including an empty string when omitted.
    The count does not participate in equality or hashing.

    Attributes:
        number: Supplied count, without validation or conversion.
    """

    def __init__(
        self,
        *args: Any,
        number: int,
        **kwargs: Any,
    ) -> None:
        """Construct the amount and attach its entry count unchanged.

        Args:
            *args: Positional arguments passed to :class:`Amount`.
            number: Entry count. Retained exactly as supplied for
                compatibility.
            **kwargs: Keyword arguments passed to :class:`Amount`, including
                ``options`` and parsed tag fields.

        Amount conversion errors propagate from :class:`Amount`.
        """
        super().__init__(*args, **kwargs)
        self.number: int = number

    def __eq__(self, other: object) -> bool:
        """Return whether ``other`` is an equal-valued amount.

        ``number`` is informational and takes no part, as in 5.0.0: a plain
        :class:`Amount` of the same value compares equal, and so do two totals
        over a different number of entries.
        """
        return super().__eq__(other)

    def __hash__(self) -> int:
        """Return the :class:`Amount` hash, matching ``__eq__``."""
        return super().__hash__()

    def __repr__(self) -> str:
        """Return the amount, currency and entry count in angle brackets."""
        return f'<{self.amount} {self.currency} in {self.number} stmts)>'


class Balance(Model):
    """A dated balance with a debit or credit status and optional amount.

    A non-empty amount string is converted to :class:`Amount`. Existing amount
    objects are retained by reference. Empty strings and ``None`` stay
    unchanged. Equality and hashing use amount and status only. The date is
    informational and does not distinguish otherwise equal balances.

    Attributes:
        status: Original debit or credit mark, or ``None``.
        amount: Amount object, an empty string, or ``None``.
        date: Supplied balance date, or ``None``, without conversion.

    Examples:
        >>> balance = Balance('C', '0.00', Date(2010, 7, 22), currency='EUR')
        >>> balance.status, balance.amount.amount
        ('C', Decimal('0.00'))
        >>> balance.date
        Date(2010, 7, 22)
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
        """Store a balance and convert a non-empty amount string if needed.

        Args:
            status: Debit or credit mark required when converting a non-empty
                amount string. Stored even when an amount object is supplied.
            amount: An :class:`Amount`, amount string, or ``None``. Existing
                objects are neither copied nor re-signed.
            date: Balance date retained without conversion.
            options: Passed to :class:`Amount` only when converting a string.
            **kwargs: Parsed fields. Only ``currency`` is used during
                conversion.

        Raises:
            ValueError: A non-empty amount string is supplied without
                ``status``.
            decimal.InvalidOperation: The amount string is not valid decimal
                text.
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
        """Return equality of balance amount and status, ignoring the date."""
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
    """Parsed fields for one transaction, linked to its owning collection.

    Available fields depend on the source bank, tags and configured processors.
    Common fields include ``amount``, ``date``, ``entry_date``, ``id``,
    references and ``purpose``. Statement metadata is copied only by an
    explicit processor, such as the default ``transaction_reference`` copier.

    Attributes:
        transactions: Owning :class:`Transactions`, retained by reference.
        data: Mutable field dictionary. Initial mapping contents are copied
            shallowly, so nested values remain shared with the caller.
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
        """Merge fields into the transaction's existing dictionary.

        Args:
            data: Fields to copy shallowly. ``None`` and empty dictionaries do
                nothing. Existing keys are overwritten, including by ``None``.

        The operation returns ``None`` and mutates this transaction's ``data``.
        It does not use the collection's string-joining or merge option rules.
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
    """A sequence of transactions with mutable statement metadata.

    Indexing, slicing, iteration and length delegate to ``transactions``.
    Repeated :meth:`parse` calls reuse the same data and transaction list.
    Create a new instance when parsing an unrelated source.

    Attributes:
        data: Statement fields keyed by tag output names. Later statement
            values replace earlier ones, including balances and references.
        transactions: Mutable ordered list of :class:`Transaction` instances.
        options: Immutable parser switches. Omitted options disable all ten.
        tags: Per-collection mapping from tag ID to parser instance. The
            mapping is copied, but tag instances are shared with its source.
        processors: Per-collection mapping of slot name to ordered callable
            lists. The mapping is copied shallowly, so default or supplied
            lists are shared. Assign a new list to customise one collection.
        transaction_boundary: Frozen set of extra tag slugs that start a new
            transaction. A following statement tag can fill the placeholder.
        DEFAULT_PROCESSORS: Default slot mapping, copied shallowly on
            construction and unpickling. Statement processors repair February
            dates, remove raw date parts and copy the statement reference. The
            details post-processor decodes structured ``:86:`` content.

    Replacing a processor slot replaces its whole list. The order is regex
    capture, pre-processors, tag conversion, post-processors, then storage.
    Pickling discards customised processors. Unpickling restores default slots,
    while retaining saved tags, metadata, transactions and options.
    """

    #: Ordered callback slots copied into each collection's processors mapping.
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
        """Return a shallow state copy with the processor mapping removed.

        Returns:
            Instance state suitable for pickle when its remaining values are
            picklable. Custom processors are omitted because closures may not
            be picklable. Other custom attributes are retained.
        """
        state = self.__dict__.copy()
        del state['processors']
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Merge pickle state into the instance and restore default processors.

        Args:
            state: Saved instance attribute mapping. Contents are applied
                without validation. Any supplied ``processors`` value is then
                replaced with a shallow copy of :attr:`DEFAULT_PROCESSORS`.

        Missing ``transaction_boundary`` and ``options`` attributes get empty
        boundaries and disabled switches to support older pickles. Existing
        saved values for those attributes are preserved. Returns ``None``.
        """
        self.__dict__.update(state)
        self.processors: Processors = self.DEFAULT_PROCESSORS.copy()
        # Pickles written by 4.x predate transaction_boundary, and pickles
        # written by 5.0.0 predate options.
        _ = self.__dict__.setdefault('transaction_boundary', frozenset())
        _ = self.__dict__.setdefault('options', Options())

    def __init__(
        self,
        processors: Processors | None = None,
        tags: dict[int | str, mt940.tags.Tag] | None = None,
        transaction_boundary: Iterable[str] | None = None,
        *,
        options: Options | None = None,
    ) -> None:
        """Create an empty collection with tag and processor overrides.

        Args:
            processors: Slot names mapped to callable lists. Supplied lists
                replace entire default slots. An empty list disables a default
                slot. Lists are shared with the supplied mapping, not copied.
            tags: Additional or overriding tag instances keyed by tag ID. The
                mapping is copied, while the instances remain shared.
            transaction_boundary: Extra tag slugs that create transaction
                blocks. A string is treated as one slug. Other iterables are
                consumed once into a ``frozenset``. Omitted or empty selects no
                extra boundaries.
            options: Parser switches. Omitted or ``None`` disables all ten
                fields.

        No tags or processors run until :meth:`parse` is called.
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
        """Currency on the first non-``None`` eligible metadata value.

        Priority is final opening, opening, intermediate opening, available,
        forward available, final closing, closing and intermediate closing
        balances, then credit and debit floor limits. The chosen value's
        ``currency`` is used, or its ``amount.currency`` when it has no
        currency attribute.

        Returns:
            A currency string, or ``None`` if the chosen metadata value has no
            usable string currency. An unusable earlier balance does not
            trigger a search through later balances. No balance gives ``None``
            as well.
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
        """Return the shared built-in tag-ID mapping without copying it.

        Returns:
            :data:`mt940.tags.TAG_BY_ID`. Constructors copy its mapping, while
            continuing to share its tag instances.
        """
        return mt940.tags.TAG_BY_ID

    def parse(self, data: str) -> list[Transaction]:
        """Parse text into this collection, retaining previously parsed state.

        Trailing whitespace, carriage returns, empty lines and standalone ``-``
        lines are removed first. Remaining tags must start at the beginning of
        a line. Unknown tag markers do not delimit a value, so their text can
        remain inside the preceding recognised tag and affect its parsing.

        For each recognised tag, pre-processors transform captured groups, the
        tag builds model values and post-processors transform the result.
        Storage happens last. Statement tags fill the last transaction if its
        ``id`` is false or missing, otherwise they append a transaction. Extra
        configured boundaries always append a placeholder. Other
        transaction-scoped tags update the last transaction or are dropped if
        none exists. Dual-scoped tags update that transaction when present,
        otherwise statement metadata.

        Args:
            data: Decoded MT940 text. This method does not open files, decode
                bytes or apply ``Options.strip_bom``. Use :func:`mt940.parse`
                for those.

        Returns:
            The instance's actual mutable ``transactions`` list, not a copy.
            Text with no recognised tag leaves existing state unchanged.

        Raises:
            RuntimeError: A recognised tag's value does not match its pattern.
            ValueError: A model date or numeric field is invalid.
            decimal.InvalidOperation: An amount is not valid decimal text.

        Custom tag and processor exceptions propagate. Parsing is not atomic.
        Earlier results and in-place processor mutations remain after a
        failure.
        """
        data = '\n'.join(self.strip(data.split('\n')))

        # Successive recognised markers delimit multiline values without
        # imposing a bank-specific limit on the number of continuation lines.
        tag_re = re.compile(
            r'^:\n?(?P<full_tag>(?P<tag>[0-9]{2}|NS)(?P<sub_tag>[A-Z])?):',
            re.MULTILINE,
        )
        matches = list(tag_re.finditer(data))

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
        """Run one tag's conversion pipeline and store the resulting fields.

        Args:
            match: A tag marker in the normalised source.
            i: Index of ``match`` in ``valid_matches``.
            valid_matches: Recognised markers ordered by their source
                positions.
            data: Normalised text from which marker offsets were calculated.

        The full tag ID selects an override before the numeric base ID. The
        value ends at the next recognised marker. Each pre-processor receives
        the previous mapping, and each post-processor receives the previous
        result. Statement tags take priority over extra transaction boundaries
        and declared tag scope. Results mutate this collection as described by
        :meth:`parse`. Exceptions from lookup, capture, conversion or
        processing propagate unchanged.
        """
        tag_id = self.normalize_tag_id(match.group('tag'))

        tag = self.tags.get(match.group('full_tag')) or self.tags[tag_id]

        if valid_matches[i + 1 : i + 2]:
            tag_data = data[match.end() : valid_matches[i + 1].start()].strip()
        else:
            tag_data = data[match.end() :].strip()

        tag_dict: dict[str, Any] = tag.parse(self, tag_data)

        for processor in self.processors.get(f'pre_{tag.slug}', []):
            tag_dict = processor(self, tag, tag_dict)

        result: Any = tag(self, tag_dict)

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
        """Merge statement fields into the trailing placeholder or append one.

        Args:
            result: Parsed statement fields, copied shallowly into transaction
                data.

        A missing or false ``id`` on the last transaction marks it as reusable,
        including a previous statement that supplied no transaction-type ID.
        Otherwise a new transaction is appended. With no transactions, an empty
        one is created first and then populated.
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
        """Merge result fields into the existing final transaction.

        Args:
            result: Fields to merge. Both incoming and existing values exposing
                ``strip`` are treated as strings. The stripped incoming value
                is appended after a newline. Other incoming values replace the
                old value, except ``None`` with
                ``Options.merge_keeps_values=True`` preserves a key that
                already exists.

        Missing keys are created even when their value is ``None``. This method
        requires at least one transaction and mutates only its ``data``
        dictionary. It does not copy nested values or apply to statement
        metadata.

        Raises:
            IndexError: The collection contains no transaction.
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
        """Return a transaction by list index or a new list for a slice.

        Args:
            key: Integer index, including negative indices, or a slice.

        Returns:
            The selected transaction or a list sharing the selected transaction
            objects. Changing the slice list does not change collection
            membership.

        Raises:
            IndexError: An integer index is out of range.
        """
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
        """Clean source lines without removing their leading indentation.

        Args:
            lines: Source lines, normally split on newline characters.

        Returns:
            A new list with all carriage returns and trailing whitespace
            removed. Empty results and lines containing only ``-`` after
            stripping are discarded. Other leading whitespace and internal
            blank spaces remain.
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
        """Convert a digit-only tag identifier to an integer.

        Args:
            tag_id: Marker text such as ``61``, ``60F`` or ``NS``.

        Returns:
            An integer for digit-only text, otherwise the unchanged string.
            Suffixed IDs keep their suffix and case.
        """
        if tag_id.isdigit():
            return int(tag_id)
        return tag_id

    def sanitize_tag_id_matches(
        self,
        matches: list[re.Match[str]],
    ) -> list[re.Match[str]]:
        """Keep marker matches whose base ID is registered in this collection.

        Args:
            matches: Source-ordered regex matches with a ``tag`` group
                containing the numeric base identifier or ``NS``.

        Returns:
            Accepted matches in source order. Unknown markers within ``:86:``
            content remain part of that value. Full suffixed IDs are not
            checked here, so a suffixed-only override also needs its base ID
            registered.
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
    """Scope marker accepted as both statement and transaction scope.

    The parser stores a dual-scoped tag such as ``:NS:`` in the current
    transaction when one exists. Before the first transaction it stores the
    data on the collection. It does not automatically write to both places. A
    configured transaction boundary is handled before these scope checks.

    The parser uses only subclass checks and never instantiates this marker.
    Direct construction follows the ``Transactions`` initialiser and behaves
    like an empty collection, preserving the historical class interface.
    """
