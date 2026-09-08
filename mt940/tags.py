"""Capture MT940 fields and convert them into model values.

Each :class:`Tag` compiles a regex with named groups. :meth:`Tag.parse` returns
those groups, pre-processors may change them, and calling the tag converts them
to a result mapping. The collection then runs post-processors and stores the
result according to the tag's scope.

:data:`TAG_BY_ID` is the built-in registry. Numeric IDs also handle suffixed
markers when no exact override exists, for example ``13`` handles ``:13D:``.
The explicitly registered balance and summary suffixes have their own classes.
:class:`StatementASNB` and :class:`StatementGLS` are opt-in variants.

Patterns describe the accepted input of this implementation. They include
bank-specific extensions and are not a complete validator for the SWIFT
standard. Most compile case-insensitively. Amount signing still depends on
:class:`mt940.options.Options` because captures retain their original case.
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

#: Parent logger for tag diagnostics, including raw values on parse failure.
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
    """Base protocol for capturing a field and producing stored model values.

    Subclasses supply a regex ``pattern`` and normally an ``id``. Override
    :meth:`__call__` for model conversion or :meth:`parse` for capture
    behaviour. Shared built-in instances must read per-parse options from the
    collection, not retain mutable state from a particular parse.

    Attributes:
        id: Registry key, either a numeric base ID or an exact suffixed string.
        RE_FLAGS: Regex flags, case-insensitive, verbose and Unicode by
            default.
        scope: Storage marker class. ``Transactions`` stores statement fields,
            ``Transaction`` updates the current transaction, and the dual
            marker uses the current transaction if one exists, otherwise the
            statement.
        pattern: Subclass regex whose named groups form the capture mapping.
        name: Class name assigned to the class during instance allocation.
        slug: Lowercase underscore-separated words matched from the class name.
            Words must have an uppercase first letter followed by lowercase
            letters. Acronym-only suffixes such as ``GLS`` are omitted.
        logger: Child logger named for the tag class. Parse diagnostics may
            include raw bank statement values.
        re: Pattern compiled once during instance initialisation.

    Tags compare by identity. Two instances with equal IDs share a hash value
    but remain different dictionary keys and set members.
    """

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
        """Compile the subclass's pattern once with its regex flags.

        Raises:
            AttributeError: The subclass supplies no ``pattern``.
            re.error: The supplied regular expression is invalid.
        """
        self.re: re.Pattern[str] = re.compile(self.pattern, self.RE_FLAGS)

    def parse(
        self, transactions: models.Transactions, value: str
    ) -> dict[str, str | None]:
        """Match the beginning of a field value and return its named groups.

        Args:
            transactions: Active collection. The base implementation does not
                use it, but overrides can inspect its metadata and options.
            value: Raw tag value, excluding its marker. The collection strips
                whitespace around this value before passing it here.

        Returns:
            A new dictionary of group names to strings or ``None`` for
            unmatched optional groups. Trailing text is allowed unless the
            pattern ends with an anchor. Regex matching does not validate dates
            or decimal amounts.

        Raises:
            RuntimeError: The value does not match. Its arguments contain a
                readable message, this tag instance and the original value.

        Successful matches log captures at debug level. Failures log the raw
        value and pattern before attempting partial-match diagnostics.
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
        """Log which individual pattern lines consume parts of a failed value.

        Args:
            value: Raw value whose complete pattern match failed.

        A successful fragment advances the remaining text. A mismatch leaves it
        unchanged. Regex lines that cannot compile independently are logged and
        skipped, so diagnostics do not replace the intended parsing exception.
        The method emits log records and does not return parsed data.
        """
        part_value = value
        for pattern in self.pattern.split('\n'):
            try:
                match = re.match(pattern, part_value, self.RE_FLAGS)
            except re.error:
                # Single lines of a pattern with multi-line groups are not
                # valid patterns on their own. Skip them instead of masking
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
        """Return the pre-processed group mapping without copying it.

        Args:
            transactions: Active collection, unused by the base implementation.
            value: Final pre-processor mapping, normally regex groups.

        Returns:
            The identical ``value`` object. Subclasses may mutate it and return
            a different mapping containing models. Consequently a
            post-processor's ``tag_dict`` can already contain converted values.
        """
        # Part of the tag protocol, the base implementation needs no context.
        del transactions
        return value

    def __new__(cls, *args: typing.Any, **kwargs: typing.Any) -> Self:
        """Allocate a tag and assign its derived metadata on the class.

        Args:
            *args: Ignored during allocation, left for a subclass initialiser.
            **kwargs: Ignored during allocation, left for a subclass
                initialiser.

        Returns:
            An uninitialised instance of the called class. ``name``, ``slug``
            and ``logger`` are assigned on that class, so all its instances
            share those metadata attributes. The slug selects processor slots.
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

        Tags compare by identity, as they did in 5.0.0, so two instances of one
        class stay distinct set members and dictionary keys. The id-based
        ``__hash__`` is consistent with that: an object is always equal to
        itself.
        """
        return self is other

    def __hash__(self) -> int:
        """Return a hash based on the tag's ``id``.

        Returns:
            The integer hash of the tag.
        """
        return hash(self.id) if isinstance(self.id, str) else self.id


class DateTimeIndication(Tag):
    """Report creation date and optional offset from ``:13:`` or ``:13D:``.

    Captures ``YYMMDDhhmm`` followed by an optional signed four-digit offset.
    Conversion returns a :class:`~mt940.models.DateTime` under ``date`` in
    statement metadata. No offset yields a naive datetime.

    Legacy conversion treats offset digits as a minute count. With
    ``Options.timezone_offset=True`` they are interpreted as hours and minutes,
    so ``+0130`` means 90 minutes instead of 130. The parser does not
    independently validate the offset's hour and minute subfields.
    """

    #: Registry ID for :class:`DateTimeIndication`.
    id: ClassVar[str | int] = 13
    #: Named capture pattern implementing the fields described by
    #: :class:`DateTimeIndication`.
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
        """Convert date groups to a report timestamp and consume offset groups.

        Args:
            transactions: Collection providing the timezone interpretation
                option.
            value: Mutable year, month, day, hour, minute and optional offset
                groups.

        Returns:
            A new ``{'date': DateTime(...)}`` mapping. ``offset_sign`` and the
            raw ``offset`` are removed from ``value``. A present offset is
            replaced there by the representation consumed by ``DateTime``.

        Raises:
            ValueError: A date component is invalid or outside its supported
                range.
        """
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
    """Statement reference from ``:20:``, stored as ``transaction_reference``.

    Captures at most 16 characters without requiring an end-of-value match. The
    default statement post-processor copies the latest reference into each
    converted ``:61:`` result. The field itself does not normally start a new
    transaction. Use ``transaction_boundary`` to select that behaviour.
    """

    #: Registry ID for :class:`TransactionReferenceNumber`.
    id: ClassVar[str | int] = 20
    #: Named capture pattern implementing the fields described by
    #: :class:`TransactionReferenceNumber`.
    pattern: ClassVar[str] = r'(?P<transaction_reference>.{0,16})'


class RelatedReference(Tag):
    """Related statement reference from ``:21:`` as ``related_reference``.

    Captures up to 16 characters and stores the result in statement metadata.
    No relation to another parsed statement is resolved automatically.
    """

    #: Registry ID for :class:`RelatedReference`.
    id: ClassVar[str | int] = 21
    #: Named capture pattern implementing the fields described by
    #: :class:`RelatedReference`.
    pattern: ClassVar[str] = r'(?P<related_reference>.{0,16})'


class AccountIdentification(Tag):
    """Account identifier from ``:25:`` as ``account_identification``.

    Captures up to 35 characters without validating IBAN structure or checksum.
    The value belongs to statement metadata and later account tags replace it.
    """

    #: Registry ID for :class:`AccountIdentification`.
    id: ClassVar[str | int] = 25
    #: Named capture pattern implementing the fields described by
    #: :class:`AccountIdentification`.
    pattern: ClassVar[str] = r'(?P<account_identification>.{0,35})'


class StatementNumber(Tag):
    """Statement and optional sequence numbers from ``:28:`` or ``:28C:``.

    Returns string fields ``statement_number`` and ``sequence_number``. Each
    accepts one to five digits and the optional sequence may have a separating
    slash. Leading zeroes are preserved. An absent sequence is ``None``.
    """

    #: Registry ID for :class:`StatementNumber`.
    id: ClassVar[str | int] = 28
    #: Named capture pattern implementing the fields described by
    #: :class:`StatementNumber`.
    pattern: ClassVar[str] = r"""
    (?P<statement_number>\d{1,5})  # 5n
    (?:/?(?P<sequence_number>\d{1,5}))?  # [/5n]
    $"""


class FloorLimitIndicator(Tag):
    """Debit or credit reporting threshold from ``:34:`` or ``:34F:``.

    Captures a three-letter currency, an optional debit or credit mark, and an
    amount. Conversion produces ``d_floor_limit`` or ``c_floor_limit`` amounts.
    An absent mark produces both. By default a space mark produces the legacy
    ``' _floor_limit'`` key. ``Options.floor_limit_blank_mark`` treats the
    space as an absent mark, making both normal keys available for currency
    lookup.
    """

    #: Registry ID for :class:`FloorLimitIndicator`.
    id: ClassVar[str | int] = 34
    #: Named capture pattern implementing the fields described by
    #: :class:`FloorLimitIndicator`.
    pattern: ClassVar[str] = r"""^
    (?P<currency>[A-Z]{3})  # 3!a Currency
    (?P<status>[DC ]?)  # 2a Debit/Credit Mark
    (?P<amount>[0-9,]{0,16})  # 15d Amount (includes decimal sign, so 16)
    $"""

    def __call__(
        self, transactions: models.Transactions, value: dict[str, typing.Any]
    ) -> dict[str, object]:
        """Build one signed floor limit or both debit and credit limits.

        Args:
            transactions: Collection providing blank-mark and amount-sign
                options.
            value: Captured ``currency``, ``status`` and ``amount`` fields.

        Returns:
            A new mapping of floor-limit keys to :class:`~mt940.models.Amount`.
            The source mapping is read without mutation. Key names use
            lowercase status even when lowercase signing is disabled.

        Raises:
            decimal.InvalidOperation: The captured amount is empty or invalid.
        """
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
    """Bank-specific ``:NS:`` text with optional two-digit line subfields.

    Lines beginning with two digits and non-empty content populate
    ``non_swift_<id>``. Later occurrences of the same ID replace earlier ones.
    ``non_swift`` retains the complete raw value, while ``non_swift_text``
    joins its content with subfield prefixes removed.

    Legacy handling can replace a free-text line after content with a paragraph
    separator. ``Options.non_swift_free_text`` preserves non-blank free text.
    The dual scope stores fields on the current transaction if one exists,
    otherwise on the statement.
    """

    #: Storage scope interpreted by :meth:`mt940.models.Transactions.parse`.
    scope: ClassVar[type[models.Transactions | models.Transaction]] = (
        models.TransactionsAndTransaction
    )
    #: Registry ID for :class:`NonSwift`.
    id: ClassVar[str | int] = 'NS'

    # NS content is bank specific and free-form, so accept anything
    # (including multi-line values whose lines do not all start with a
    # two-digit sub-tag). `__call__` extracts the `2!n35x` structure per
    # line where present.
    #: Named capture pattern implementing the fields described by
    #: :class:`NonSwift`.
    pattern: ClassVar[str] = r"""
    (?P<non_swift>[\s\S]*)
    $"""
    #: Two-digit non-SWIFT line ID followed by unrestricted same-line content.
    sub_pattern: ClassVar[str] = r"""
    (?P<ns_id>\d{2})(?P<ns_data>.{0,})
    """
    #: Compiled line pattern used to extract non-SWIFT subfields.
    sub_pattern_m: ClassVar[re.Pattern[str]] = re.compile(
        sub_pattern, re.IGNORECASE | re.VERBOSE | re.UNICODE
    )

    def __call__(
        self, transactions: models.Transactions, value: dict[str, typing.Any]
    ) -> dict[str, object]:
        """Add per-line subfields and a readable text version to the capture.

        Args:
            transactions: Collection providing the free-text preservation
                option.
            value: Mutable mapping containing the raw ``non_swift`` string.

        Returns:
            The same mapping with ``non_swift_<id>`` entries and
            ``non_swift_text``. The original ``non_swift`` string is retained.
            Consecutive blank separators are collapsed according to the legacy
            paragraph rules.

        Raises:
            KeyError: The capture has no ``non_swift`` field.
        """
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
    """Capture and convert opening, closing and available balances.

    The pattern accepts a debit or credit mark, ``YYMMDD``, three currency
    characters and a decimal-comma amount. Conversion stores a
    :class:`~mt940.models.Balance` under the concrete tag's slug. Currency text
    is retained without ISO-code validation. The class-derived slug determines
    the output key independently of the tag ID. The collection's currency
    lookup checks a fixed set of balance keys. A custom subclass with a
    different slug is not included automatically, even if its ID matches a
    built-in balance tag.
    """

    #: Named capture pattern implementing the fields described by
    #: :class:`BalanceBase`.
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
        """Build an amount, date and balance from captured fields.

        Args:
            transactions: Collection providing amount-sign options.
            value: Mutable capture mapping with status, date, currency and
                amount.

        Returns:
            A new mapping from this tag's slug to a
            :class:`~mt940.models.Balance`. The source ``amount`` is replaced
            with an ``Amount`` and a ``date`` model is added. Raw date groups
            remain in the source mapping.

        Raises:
            ValueError: The calendar date is invalid.
            decimal.InvalidOperation: The amount cannot be converted to a
                decimal.
        """
        data = super().__call__(transactions, value)
        options = _options_of(transactions)
        data['amount'] = models.Amount(**data, options=options)
        data['date'] = models.Date(**data)
        return {self.slug: models.Balance(**data, options=options)}


class OpeningBalance(BalanceBase):
    """Opening balance (``:60:``)."""

    #: Registry ID for :class:`OpeningBalance`.
    id: ClassVar[str | int] = 60


class FinalOpeningBalance(BalanceBase):
    """Final opening balance (``:60F:``)."""

    #: Registry ID for :class:`FinalOpeningBalance`.
    id: ClassVar[str | int] = '60F'


class IntermediateOpeningBalance(BalanceBase):
    """Intermediate opening balance (``:60M:``)."""

    #: Registry ID for :class:`IntermediateOpeningBalance`.
    id: ClassVar[str | int] = '60M'


class Statement(Tag):
    """Transaction line from ``:61:`` with amount, references and dates.

    Captured fields are ``year``, ``month`` and ``day`` for the value date,
    optional ``entry_month`` and ``entry_day``, ``status``, optional
    ``funds_code``, ``amount``, optional transaction-type ``id``,
    ``customer_reference``, optional ``bank_reference`` and ``extra_details``.
    Entry parts accept digits or spaces. The customer reference is capped at 16
    characters and the bank reference, excluding its ``//`` delimiter, at 23.
    Extra details have no length cap.

    Conversion adds ``date`` and replaces ``amount`` with an amount model. A
    numeric entry month and day produce ``entry_date`` and its compatibility
    alias ``guessed_entry_date``. Default post-processors remove raw date parts
    and copy the latest statement reference. Optional groups remain ``None``
    unless a processor removes or replaces them.

    The collection reuses a trailing transaction with a false or missing
    ``id``. Otherwise this tag starts a transaction. A missing transaction-type
    ID can therefore cause successive statement lines to share a transaction.
    """

    #: Registry ID for :class:`Statement`.
    id: ClassVar[str | int] = 61
    #: Storage scope interpreted by :meth:`mt940.models.Transactions.parse`.
    scope: ClassVar[type[models.Transactions | models.Transaction]] = (
        models.Transaction
    )
    #: Named capture pattern implementing the fields described by
    #: :class:`Statement`.
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
        """Convert the amount and dates, inferring an entry year if possible.

        Args:
            transactions: Collection supplying a currency fallback and sign
                options.
            value: Mutable statement capture mapping after pre-processing.

        Returns:
            The same mapping with model values. Missing ``currency`` uses the
            collection currency, but an existing ``None`` is retained. Entry
            dates initially use the value-date year. A difference of at least
            330 days adjusts the entry year by one toward the value date. Both
            entry-date keys refer to the same resolved model.

        Raises:
            ValueError: The value date or initial same-year entry date is
                invalid.
            decimal.InvalidOperation: The amount text is invalid.

        The initial entry date is validated before its year can be corrected.
        """
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
            # `entry_date` and `guessed_entry_date` expose the resolved value.
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
    """Opt-in statement pattern allowing ASN Bank's longer customer reference.

    The customer reference accepts up to 34 characters, allowing account
    numbers that exceed the default 16-character field. Its greedy capture can
    include ``//`` within those 34 characters. Bank reference and extra details
    are capped at 16 and 34 characters respectively. Conversion is inherited
    from :class:`Statement`.

    Register an instance under numeric ID ``61`` to replace the default parser.
    Its derived slug remains ``statement``, so default statement processors
    run.
    """

    #: Named capture pattern implementing the fields described by
    #: :class:`StatementASNB`.
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
        """Apply the standard statement conversion to ASN-specific captures.

        Args:
            transactions: Collection supplying currency and parser options.
            value: Mutable mapping returned by this variant's pattern.

        Returns:
            The mapping converted by :meth:`Statement.__call__`. Amount and
            date conversion errors propagate unchanged.
        """
        return super().__call__(transactions, value)


class StatementGLS(Statement):
    """Opt-in statement pattern for long GLS and Atruvia customer references.

    The customer reference continues until ``//`` or a newline with no length
    cap. Bank references retain the default 23-character cap, and extra details
    remain unbounded. The inherited conversion and ``statement`` processor slug
    are unchanged.

    Example:
        >>> import mt940
        >>> source = ':61:240101C1,00NTRFA-LONG-CUSTOMER-REFERENCE//BANK'
        >>> parsed = mt940.parse(source, tags={61: StatementGLS()})
        >>> parsed[0].data['customer_reference']
        'A-LONG-CUSTOMER-REFERENCE'
    """

    #: Named capture pattern implementing the fields described by
    #: :class:`StatementGLS`.
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

    #: Registry ID for :class:`ClosingBalance`.
    id: ClassVar[str | int] = 62


class IntermediateClosingBalance(ClosingBalance):
    """Intermediate closing balance (``:62M:``)."""

    #: Registry ID for :class:`IntermediateClosingBalance`.
    id: ClassVar[str | int] = '62M'


class FinalClosingBalance(ClosingBalance):
    """Final closing balance (``:62F:``)."""

    #: Registry ID for :class:`FinalClosingBalance`.
    id: ClassVar[str | int] = '62F'


class AvailableBalance(BalanceBase):
    """Available balance (``:64:``)."""

    #: Registry ID for :class:`AvailableBalance`.
    id: ClassVar[str | int] = 64


class ForwardAvailableBalance(BalanceBase):
    """Forward available balance (``:65:``)."""

    #: Registry ID for :class:`ForwardAvailableBalance`.
    id: ClassVar[str | int] = 65


class TransactionDetails(Tag):
    """Transaction information from ``:86:`` as ``transaction_details``.

    The capture pattern accepts all characters, including newlines. The default
    parser then reproduces the historical nine-chunk, 65-character limit unless
    ``Options.unbounded_details`` is enabled. A subclass using a different
    pattern keeps its own capture unchanged.

    The default post-processor decodes recognised structured subfields and GVC
    purpose keywords. Unstructured text remains in ``transaction_details``.
    This tag updates the current transaction and is dropped if none exists.
    """

    #: Registry ID for :class:`TransactionDetails`.
    id: ClassVar[str | int] = 86
    #: Storage scope interpreted by :meth:`mt940.models.Transactions.parse`.
    scope: ClassVar[type[models.Transactions | models.Transaction]] = (
        models.Transaction
    )
    # The SWIFT spec caps this field at 6 lines of 65 characters, but many
    # banks send more. The capture is unbounded: the parser in
    # `models.Transactions.parse` already limits the value to this tag's own
    # slice of the statement. `parse` below applies the 5.0.0 cap of nine
    # 65-character chunks unless `Options.unbounded_details` is on.
    #: Named capture pattern implementing the fields described by
    #: :class:`TransactionDetails`.
    pattern: ClassVar[str] = r"""
    (?P<transaction_details>[\s\S]*)
    """

    def parse(
        self, transactions: models.Transactions, value: str
    ) -> dict[str, str | None]:
        """Capture detail text and apply the optional legacy capture limit.

        Args:
            transactions: Collection providing ``unbounded_details``.
            value: Raw tag value without its marker.

        Returns:
            A new group dictionary whose ``transaction_details`` value is
            limited by :data:`_LEGACY_DETAILS_RE` when the option is disabled
            and the instance pattern equals the built-in pattern. Additional
            subclass groups are preserved.

        Raises:
            RuntimeError: A custom pattern does not match the value.
            KeyError: A capped pattern result lacks ``transaction_details``.
        """
        data = super().parse(transactions, value)
        capped = (
            not _options_of(transactions).unbounded_details
            and self.pattern == TransactionDetails.pattern
        )
        if capped:
            details = data['transaction_details'] or ''
            match = _LEGACY_DETAILS_RE.match(details)
            data['transaction_details'] = match.group(0) if match else ''
        return data


class SumEntries(Tag):
    """Base parser for entry counts and total amounts in ``:90:`` fields.

    Captures ``number`` as digit text, ``currency`` as three characters and
    ``amount`` as decimal-comma text. :class:`SumDebitEntries` and
    :class:`SumCreditEntries` provide the required sign and suffixed tag IDs.
    The count is retained as a string even though ``SumAmount`` annotates its
    constructor argument as an integer.

    The bare base class remains registered for compatibility, but it has no
    ``status`` value. Converting a bare ``:90:`` therefore raises
    ``AttributeError``. Use a suffixed debit or credit summary, or a custom
    subclass that supplies a status.
    """

    #: Registry ID for :class:`SumEntries`.
    id: ClassVar[str | int] = 90
    #: Named capture pattern implementing the fields described by
    #: :class:`SumEntries`.
    pattern: ClassVar[str] = r"""^
    (?P<number>\d*)
    (?P<currency>.{3})  # 3!a Currency
    (?P<amount>[\d,]{1,15})  # 15d Amount
    """
    #: Debit or credit mark supplied to the summary amount constructor.
    status: ClassVar[str]

    def __call__(
        self, transactions: models.Transactions, value: dict[str, typing.Any]
    ) -> dict[str, object]:
        """Build a total amount and attach the captured entry count unchanged.

        Args:
            transactions: Collection providing amount-sign options.
            value: Mutable capture mapping containing number, currency and
                amount.

        Returns:
            A new mapping from the tag's slug to
            :class:`~mt940.models.SumAmount`. The source mapping gains this
            class's ``status`` field.

        Raises:
            AttributeError: The concrete class does not define ``status``.
            decimal.InvalidOperation: The amount cannot be converted to a
                decimal.
        """
        data = super().__call__(transactions, value)
        data['status'] = self.status
        return {
            self.slug: models.SumAmount(
                **data, options=_options_of(transactions)
            )
        }


class SumDebitEntries(SumEntries):
    """Number and sum of debit entries (``:90D:``)."""

    #: Debit or credit mark supplied to the summary amount constructor.
    status: ClassVar[str] = 'D'
    #: Registry ID for :class:`SumDebitEntries`.
    id: ClassVar[str | int] = '90D'


class SumCreditEntries(SumEntries):
    """Number and sum of credit entries (``:90C:``)."""

    #: Debit or credit mark supplied to the summary amount constructor.
    status: ClassVar[str] = 'C'
    #: Registry ID for :class:`SumCreditEntries`.
    id: ClassVar[str | int] = '90C'


@enum.unique
class Tags(enum.Enum):
    """Enumeration of shared built-in parser instances.

    Each member's ``value`` is a :class:`Tag` instance. :data:`TAG_BY_ID`
    indexes these same instances by their IDs. Optional bank variants are
    intentionally absent and can be supplied through the collection's ``tags``
    argument. Members do not contain per-statement mutable state.
    """

    #: Shared :class:`DateTimeIndication` parser instance.
    DATE_TIME_INDICATION = DateTimeIndication()
    #: Shared :class:`TransactionReferenceNumber` parser instance.
    TRANSACTION_REFERENCE_NUMBER = TransactionReferenceNumber()
    #: Shared :class:`RelatedReference` parser instance.
    RELATED_REFERENCE = RelatedReference()
    #: Shared :class:`AccountIdentification` parser instance.
    ACCOUNT_IDENTIFICATION = AccountIdentification()
    #: Shared :class:`StatementNumber` parser instance.
    STATEMENT_NUMBER = StatementNumber()
    #: Shared :class:`OpeningBalance` parser instance.
    OPENING_BALANCE = OpeningBalance()
    #: Shared :class:`IntermediateOpeningBalance` parser instance.
    INTERMEDIATE_OPENING_BALANCE = IntermediateOpeningBalance()
    #: Shared :class:`FinalOpeningBalance` parser instance.
    FINAL_OPENING_BALANCE = FinalOpeningBalance()
    #: Shared :class:`Statement` parser instance.
    STATEMENT = Statement()
    #: Shared :class:`ClosingBalance` parser instance.
    CLOSING_BALANCE = ClosingBalance()
    #: Shared :class:`IntermediateClosingBalance` parser instance.
    INTERMEDIATE_CLOSING_BALANCE = IntermediateClosingBalance()
    #: Shared :class:`FinalClosingBalance` parser instance.
    FINAL_CLOSING_BALANCE = FinalClosingBalance()
    #: Shared :class:`AvailableBalance` parser instance.
    AVAILABLE_BALANCE = AvailableBalance()
    #: Shared :class:`ForwardAvailableBalance` parser instance.
    FORWARD_AVAILABLE_BALANCE = ForwardAvailableBalance()
    #: Shared :class:`TransactionDetails` parser instance.
    TRANSACTION_DETAILS = TransactionDetails()
    #: Shared :class:`FloorLimitIndicator` parser instance.
    FLOOR_LIMIT_INDICATOR = FloorLimitIndicator()
    #: Shared :class:`NonSwift` parser instance.
    NON_SWIFT = NonSwift()
    #: Shared :class:`SumEntries` parser instance.
    SUM_ENTRIES = SumEntries()
    #: Shared :class:`SumDebitEntries` parser instance.
    SUM_DEBIT_ENTRIES = SumDebitEntries()
    #: Shared :class:`SumCreditEntries` parser instance.
    SUM_CREDIT_ENTRIES = SumCreditEntries()


#: Mapping of tag id (``int`` or ``str``) to the tag instance that parses it.
TAG_BY_ID = {t.value.id: t.value for t in Tags}
