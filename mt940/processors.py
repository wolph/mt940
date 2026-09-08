"""Transform captured tag dictionaries before and after model construction.

Pre-processors receive ``transactions``, ``tag`` and ``tag_dict`` and return
the mapping supplied to the next step. Post-processors additionally receive
``result`` and return its replacement. Both kinds may mutate their input. They
run in configured list order and their exceptions propagate unchanged. The
current tag's result has not yet been stored on the collection.

Register functions under ``pre_<tag.slug>`` or ``post_<tag.slug>`` in
``Transactions.processors`` or the high-level parsing functions. A supplied
list replaces the entire default slot. For example, to add currency while
keeping the default date repair:

Example:
    >>> import mt940
    >>> defaults = mt940.models.Transactions.DEFAULT_PROCESSORS
    >>> configured = {
    ...     'pre_statement': [
    ...         *defaults['pre_statement'],
    ...         add_currency_pre_processor('EUR'),
    ...     ],
    ... }
    >>> result = mt940.parse(
    ...     ':61:240101C1,25NTRFNONREF', processors=configured
    ... )
    >>> result[0].data['amount']
    <1.25 EUR>
"""

from __future__ import annotations

import calendar
import collections
import functools
import re
from typing import TYPE_CHECKING, Any

# Runtime re-exports: 5.0.0 exposed the processor protocols here.
from ._types import PostProcessor, PreProcessor  # noqa: TC001
from .options import Options

if TYPE_CHECKING:
    from . import models, tags


def add_currency_pre_processor(
    currency: str,
    overwrite: bool = True,
) -> PreProcessor:
    """Create a processor that assigns a currency to captured tag fields.

    Args:
        currency: Value to store under ``currency``, without validating it.
        overwrite: Replace an existing value when true. When false, even an
            existing ``None`` is retained because key presence is tested.

    Returns:
        A :class:`PreProcessor` closure that mutates and returns the same
        mapping. Register it before amount construction, for example in
        ``pre_statement`` for files without a balance carrying the currency.
    """

    def _add_currency_pre_processor(
        transactions: models.Transactions,
        tag: tags.Tag,
        tag_dict: dict[str, Any],
        *args: Any,
    ) -> dict[str, Any]:
        """Set the captured currency according to the factory's overwrite rule.

        Args:
            transactions: Unused collection context required by the protocol.
            tag: Unused tag context required by the protocol.
            tag_dict: Mutable capture mapping receiving the currency.
            *args: Ignored compatibility arguments.

        Returns:
            The same ``tag_dict`` object, possibly with ``currency`` replaced.
        """
        if 'currency' not in tag_dict or overwrite:
            tag_dict['currency'] = currency
        return tag_dict

    return _add_currency_pre_processor


def date_fixup_pre_processor(
    transactions: models.Transactions,
    tag: tags.Tag,
    tag_dict: dict[str, Any],
    *args: Any,
) -> dict[str, Any]:
    """Clamp an excessive February day before constructing a date.

    Only the exact month string ``02`` is adjusted. The leap-year calculation
    uses the captured integer year directly, before the model adds 2000 to
    short years. Other months and invalid low day numbers remain untouched.
    This processor is registered in the default ``pre_statement`` slot.

    Args:
        transactions: Unused collection context.
        tag: Unused tag context.
        tag_dict: Capture mapping containing ``month``, ``year`` and ``day``.
        *args: Ignored compatibility arguments.

    Returns:
        The same mapping. An excessive February ``day`` becomes the last valid
        day as a string. Entry-date fields are not adjusted.

    Raises:
        KeyError: A required date field is absent.
        ValueError: A February year or day is not valid integer text.
    """
    if tag_dict['month'] == '02':
        year = int(tag_dict['year'], 10)
        _, max_month_day = calendar.monthrange(year, 2)
        if int(tag_dict['day'], 10) > max_month_day:
            tag_dict['day'] = str(max_month_day)
    return tag_dict


def date_cleanup_post_processor(
    transactions: models.Transactions,
    tag: tags.Tag,
    tag_dict: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    """Remove raw date components after the statement has built date objects.

    Args:
        transactions: Unused collection context.
        tag: Unused tag context.
        tag_dict: Unused capture mapping, which may also be ``result``.
        result: Mutable result from the tag or preceding post-processor.

    Returns:
        The same result without ``day``, ``month``, ``year``, ``entry_day`` or
        ``entry_month``. Missing keys are harmless. Converted ``date``,
        ``entry_date`` and ``guessed_entry_date`` values are retained.
    """
    for k in ('day', 'month', 'year', 'entry_day', 'entry_month'):
        result.pop(k, None)
    return result


def mBank_set_transaction_code(
    transactions: models.Transactions,
    tag: tags.Tag,
    tag_dict: dict[str, Any],
    *args: Any,
) -> dict[str, Any]:
    """Extract the leading numeric transaction code from mBank details.

    Args:
        transactions: Unused collection context.
        tag: Tag whose slug selects the raw detail value in ``tag_dict``.
        tag_dict: Mutable capture mapping containing that raw string.
        *args: Ignored compatibility arguments.

    Returns:
        The same mapping with integer ``transaction_code`` added. The code is
        the text before the first space within the first semicolon-delimited
        field. The original detail string is retained.

    Raises:
        KeyError: The tag slug is absent from ``tag_dict``.
        ValueError: The extracted code cannot be converted to an integer.
    """
    tag_value = tag_dict[tag.slug]
    tag_dict['transaction_code'] = int(
        tag_value.split(';')[0].split(' ', 1)[0]
    )
    return tag_dict


#: mBank IPH marker with optional masking X characters and up to 14 digits.
iph_id_re = re.compile(r' ID IPH: X*(?P<iph_id>\d{0,14});')


def mBank_set_iph_id(
    transactions: models.Transactions,
    tag: tags.Tag,
    tag_dict: dict[str, Any],
    *args: Any,
) -> dict[str, Any]:
    """Extract an mBank IPH virtual-account identifier when present.

    Args:
        transactions: Unused collection context.
        tag: Tag whose slug selects the raw detail string.
        tag_dict: Mutable capture mapping containing that string.
        *args: Ignored compatibility arguments.

    Returns:
        The same mapping. The first `` ID IPH: `` field matching
        :data:`mt940.processors.iph_id_re` sets ``iph_id`` to its captured
        digits as a string. Leading masking ``X`` characters are discarded. No
        match leaves any existing value unchanged. An empty captured digit
        string is allowed.

    Raises:
        KeyError: The tag slug is absent from ``tag_dict``.
    """
    matches = iph_id_re.search(tag_dict[tag.slug])
    if matches:
        tag_dict['iph_id'] = matches.group('iph_id')
    return tag_dict


#: mBank TNR marker followed by one space or newline and a digit-dot-digit ID.
tnr_re = re.compile(r'TNR:[ \n](?P<tnr>\d+\.\d+)', flags=re.MULTILINE)


def mBank_set_tnr(
    transactions: models.Transactions,
    tag: tags.Tag,
    tag_dict: dict[str, Any],
    *args: Any,
) -> dict[str, Any]:
    """Extract the transaction number carried in an mBank ``TNR:`` field.

    Args:
        transactions: Unused collection context.
        tag: Tag whose slug selects the raw detail string.
        tag_dict: Mutable capture mapping containing that string.
        *args: Ignored compatibility arguments.

    Returns:
        The same mapping with ``tnr`` set to the first matching number as text,
        including its decimal point. No match preserves any existing value. The
        processor extracts the identifier without checking its uniqueness
        within or across statements.

    Raises:
        KeyError: The tag slug is absent from ``tag_dict``.
    """
    matches = tnr_re.search(tag_dict[tag.slug])
    if matches:
        tag_dict['tnr'] = matches.group('tnr')
    return tag_dict


#: The structured ``:86:`` sub-fields and the keys they land under, as in
#: release 5.0.0: ``?31`` is prepended to the name.
DETAIL_KEYS = {
    '': 'transaction_code',
    '00': 'posting_text',
    '10': 'prima_nota',
    '20': 'purpose',
    '30': 'applicant_bin',
    '31': 'applicant_name',
    '32': 'applicant_name',
    '34': 'return_debit_notes',
    '35': 'recipient_name',
    '60': 'additional_purpose',
}

#: The same mapping with ``?31``, the counterparty account (usually an IBAN,
#: sometimes a plain account number), under its own key. This is the 4.x
#: mapping, selected by :attr:`mt940.options.Options.applicant_iban`
#: (issue #132). ``?32`` and ``?33`` together hold the name.
DETAIL_KEYS_APPLICANT_IBAN = {**DETAIL_KEYS, '31': 'applicant_iban'}

#: Case-sensitive four-character GVC keywords mapped to result field names.
#: The empty key stores purpose text without a recognised keyword. Historical
#: field spellings, including applicant_bin and debitor_identifier, are
#: retained.
GVC_KEYS = {
    '': 'purpose',
    'IBAN': 'gvc_applicant_iban',
    'BIC ': 'gvc_applicant_bin',
    'EREF': 'end_to_end_reference',
    'MREF': 'additional_position_reference',
    'CRED': 'applicant_creditor_id',
    'PURP': 'purpose_code',
    'SVWZ': 'purpose',
    'MDAT': 'additional_position_date',
    'ABWA': 'deviate_applicant',
    'ABWE': 'deviate_recipient',
    'SQTP': 'FRST_ONE_OFF_RECC',
    'ORCR': 'old_SEPA_CI',
    'ORMR': 'old_SEPA_additional_position_reference',
    'DDAT': 'settlement_tag',
    'KREF': 'customer_reference',
    'DEBT': 'debitor_identifier',
    'COAM': 'compensation_amount',
    'OAMT': 'original_amount',
}

#: Every GVC keyword (``EREF``, ``SVWZ``, ...) is exactly this wide.
_GVC_KEY_LENGTH = 4


def _options_of(transactions: models.Transactions) -> Options:
    """Return the options of the collection being parsed.

    Callers that pass something without options, as older code did with
    ``None``, get the 5.0.0 defaults.

    Args:
        transactions: The collection being parsed.

    Returns:
        The options to honour.
    """
    options: object = getattr(transactions, 'options', None)
    return options if isinstance(options, Options) else Options()


def _parse_segments(detail_str: str) -> collections.OrderedDict[str, str]:
    """Split structured details at ``?`` followed by two identifier characters.

    Args:
        detail_str: Flattened structured detail text. Identifiers are read as
            two characters without validating that they are digits.

    Returns:
        An ordered mapping from subfield ID to text. Text before the first
        complete delimiter is stored under ``''``. Repeated IDs replace their
        earlier content but retain their first insertion position. A trailing
        incomplete delimiter stops scanning. With no complete delimiter, no
        segments are returned.

    Example:
        >>> list(_parse_segments('123?00Transfer?20First?20Last').items())
        [('', '123'), ('00', 'Transfer'), ('20', 'Last')]
    """
    tmp: collections.OrderedDict[str, str] = collections.OrderedDict()
    segment = ''
    segment_type = ''

    for index, char in enumerate(detail_str):
        if char != '?':
            segment += char
            continue

        if index + 2 >= len(detail_str):
            break

        # Finalise the current segment. If a segment type exists, skip the
        # first two header characters.
        tmp[segment_type] = segment if not segment_type else segment[2:]
        segment_type = detail_str[index + 1] + detail_str[index + 2]
        segment = ''

    if segment_type:
        tmp[segment_type] = segment if not segment_type else segment[2:]

    return tmp


def _process_segments(
    tmp: collections.OrderedDict[str, str],
    detail_keys: dict[str, str] = DETAIL_KEYS,
) -> dict[str, list[str]]:
    """Group structured subfield contents under their output field names.

    Args:
        tmp: Ordered segment mapping from :func:`_parse_segments`.
        detail_keys: Direct subfield-to-output mapping. It must contain ``20``,
            ``32`` and ``60`` if their continuation cases are encountered.

    Returns:
        A new mapping from field names to ordered lists of fragments. Direct
        mappings take precedence. ``33`` continues ``32``, remaining ``2x``
        subfields continue ``20``, and ``61`` through ``65`` continue ``60``.
        Unknown subfields are ignored. Continuation purpose fragments lose a
        dangling `` BIC`` or `` IBAN`` suffix. Input mappings are not mutated.

    Raises:
        KeyError: A continuation needs a missing base key in ``detail_keys``.
    """
    result: collections.defaultdict[str, list[str]] = collections.defaultdict(
        list
    )
    for key, value in tmp.items():
        if key in detail_keys:
            result[detail_keys[key]].append(value)
        elif key == '33':
            key32 = detail_keys['32']
            result[key32].append(value)
        elif key.startswith('2'):
            # Some banks append a bare ' BIC'/' IBAN' label with no value at
            # the end of a detail segment (issue #109). Strip the dangling
            # label so it does not pollute the purpose. Segment keys are
            # always two characters (see _parse_segments), so the historical
            # '29'/'28D' key checks could never match the IBAN case -- the
            # label is matched on the value instead.
            purpose = value
            for label in (' BIC', ' IBAN'):
                if purpose.endswith(label):
                    purpose = purpose.removesuffix(label).rstrip()
                    break
            key20 = detail_keys['20']
            result[key20].append(purpose)
        elif key in {'60', '61', '62', '63', '64', '65'}:
            key60 = detail_keys['60']
            result[key60].append(value)
    return result


def _join_result(
    result: dict[str, list[str]],
    space: bool,
    detail_keys: dict[str, str] = DETAIL_KEYS,
) -> dict[str, str | None]:
    """Join fragment lists and include every configured output field.

    Args:
        result: Output field names mapped to ordered text fragments.
        space: Insert one space between fragments when true. Otherwise join
            directly. Existing fragment whitespace is retained.
        detail_keys: Subfield mapping whose unique values define output keys.

    Returns:
        A new dictionary containing all configured output fields. Missing or
        empty joined content becomes ``None``. Fields present only in
        ``result`` and absent from ``detail_keys.values()`` are discarded.
    """
    joined_result: dict[str, str | None] = {}
    for key in detail_keys.values():
        if space:
            value = ' '.join(result.get(key, []))
        else:
            value = ''.join(result.get(key, []))
        joined_result[key] = value or None
    return joined_result


def _parse_mt940_details(
    detail_str: str,
    space: bool = False,
    *,
    detail_keys: dict[str, str] = DETAIL_KEYS,
) -> dict[str, str | None]:
    """Decode structured detail subfields into named strings or ``None``.

    Args:
        detail_str: Structured detail text with line boundaries already
            removed.
        space: Insert a space between fragments belonging to the same field.
        detail_keys: Subfield mapping, normally :data:`DETAIL_KEYS` or
            :data:`DETAIL_KEYS_APPLICANT_IBAN`.

    Returns:
        New mapping with all configured output names. Missing or empty fields
        are ``None``. Repeated subfield IDs keep their last content before
        related subfields are joined. GVC purpose keywords are not decoded
        here.

    Example:
        >>> _parse_mt940_details('123?00Transfer?20Invoice?21123')['purpose']
        'Invoice123'
        >>> _parse_mt940_details('123?00Transfer?20Invoice?21123', space=True)[
        ...     'purpose'
        ... ]
        'Invoice 123'
    """
    tmp = _parse_segments(detail_str)
    result = _process_segments(tmp, detail_keys)
    return _join_result(result, space, detail_keys)


def _parse_mt940_gvcodes(
    purpose: str,
    *,
    keep_leading_text: bool = False,
) -> dict[str, str | None]:
    """Split purpose text at recognised four-character GVC keywords plus ``+``.

    Matching is case-sensitive. The ``BIC`` keyword includes a trailing space.
    Unknown keywords stay in text. A repeated keyword replaces its earlier
    value. Text preceding the first recognised keyword is discarded, and later
    segments mapped to the same output name overwrite earlier ones.

    Args:
        purpose: Flattened purpose text to inspect.
        keep_leading_text: Ignore a plus sign in the first four characters as a
            possible keyword terminator. The default preserves the legacy
            empty-key interpretation, which can drop preceding free text. This
            flag does not retain text preceding a genuine GVC keyword.

    Returns:
        New mapping containing every output name in
        :data:`mt940.processors.GVC_KEYS`, with missing values set to ``None``.
        Without a recognised keyword the remaining text becomes ``purpose``.

    Example:
        >>> parsed = _parse_mt940_gvcodes('EREF+ABC SVWZ+Invoice 123')
        >>> parsed['end_to_end_reference'], parsed['purpose']
        ('ABC ', 'Invoice 123')
    """
    result: dict[str, str | None] = dict.fromkeys(GVC_KEYS.values())

    tmp: dict[str, str] = {}
    segment_type: str | None = None
    text = ''

    for index, char in enumerate(purpose):
        # Detect the beginning of a GVC segment: if a '+' is encountered
        # and the four characters preceding it form a valid GVC key. GVC
        # keywords are four characters wide, so a '+' before index 4 cannot
        # terminate one. Without the guard a negative
        # ``purpose[index - 4:index]`` slice wraps to the empty string, which
        # matches the empty-string GVC key and drops the text in front of a
        # literal '+'. That is what 5.0.0 did.
        if (
            char == '+'
            and (index >= _GVC_KEY_LENGTH or not keep_leading_text)
            and purpose[index - _GVC_KEY_LENGTH : index] in GVC_KEYS
        ):
            if segment_type:
                tmp[segment_type] = text[:-_GVC_KEY_LENGTH]
                text = ''
            else:
                text = ''
            segment_type = purpose[index - _GVC_KEY_LENGTH : index]
        else:
            text += char

    if segment_type:
        tmp[segment_type] = text
    else:
        tmp[''] = text

    for key, value in tmp.items():
        result[GVC_KEYS[key]] = value

    return result


def transaction_details_post_processor(
    transactions: models.Transactions,
    tag: tags.Tag,
    tag_dict: dict[str, Any],
    result: dict[str, Any],
    space: bool = False,
) -> dict[str, Any]:
    """Decode structured ``:86:`` fields and optional GVC purpose keywords.

    Line boundaries are removed for detection and structured decoding. Only
    text starting with three digits, ``?`` and two digits is treated as
    structured. Unstructured input leaves ``result`` unchanged, including its
    original ``transaction_details`` text. Structured input removes that raw
    field after adding all mapped outputs, including ``None`` for missing
    fields.

    Args:
        transactions: Collection supplying ``applicant_iban`` and
            ``gvc_leading_text`` options. Missing options use disabled
            defaults.
        tag: Unused tag context.
        tag_dict: Capture mapping containing raw ``transaction_details`` text.
        result: Mutable result mapping receiving decoded fields. It must
            contain ``transaction_details`` when input is structured.
        space: Insert a space between structured fragments of the same field.

    Returns:
        The same result mapping. Structured fields overwrite existing values.
        Purpose text containing any GVC keyword is additionally decoded into
        every :data:`mt940.processors.GVC_KEYS` output, even if some outputs
        are ``None``. A trailing bare `` BIC`` is removed from the resulting
        purpose.

    Raises:
        KeyError: Required ``transaction_details`` is absent from an input
            mapping or the structured result.
    """
    options = _options_of(transactions)
    detail_keys = (
        DETAIL_KEYS_APPLICANT_IBAN if options.applicant_iban else DETAIL_KEYS
    )
    details = tag_dict['transaction_details']
    details = ''.join(detail.strip('\n\r') for detail in details.splitlines())

    if re.match(r'^\d{3}\?\d{2}', details):
        result.update(
            _parse_mt940_details(details, space=space, detail_keys=detail_keys)
        )

        purpose = result.get('purpose')

        if purpose and any(gvk in purpose for gvk in GVC_KEYS if gvk):
            result.update(
                _parse_mt940_gvcodes(
                    result['purpose'],
                    keep_leading_text=options.gvc_leading_text,
                )
            )

        if result.get('purpose'):
            # Remove trailing "BIC" without an actual BIC value
            result['purpose'] = result['purpose'].removesuffix(' BIC')

        del result['transaction_details']

    return result


#: Partial of :func:`transaction_details_post_processor` with ``space=True``.
#: Register it in place of the default details post-processor to separate
#: fragments with spaces. Its remaining arguments and mutations are identical.
transaction_details_post_processor_with_space = functools.partial(
    transaction_details_post_processor, space=True
)
transaction_details_post_processor_with_space.__doc__ = """
A variant of transaction_details_post_processor that includes spaces between
segments.
"""


def transactions_to_transaction(
    *keys: str,
) -> PostProcessor:
    """Create a processor that copies selected statement metadata.

    Args:
        *keys: Metadata keys to copy in the supplied order. Missing keys are
            ignored. Present values, including ``None``, overwrite the result.

    Returns:
        A :class:`PostProcessor` closure that mutates and returns its result.
        Values are shared by reference. The default statement slot uses this to
        copy ``transaction_reference`` from the latest ``:20:``.

    Example:
        >>> import mt940
        >>> statement = mt940.models.Transactions()
        >>> statement.data['account_identification'] = 'ACCOUNT'
        >>> copy_account = transactions_to_transaction(
        ...     'account_identification'
        ... )
        >>> copy_account(statement, mt940.tags.Statement(), {}, {})
        {'account_identification': 'ACCOUNT'}
    """

    def _transactions_to_transaction(
        transactions: models.Transactions,
        tag: tags.Tag,
        tag_dict: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Copy the factory's selected statement fields into the result.

        Args:
            transactions: Collection providing statement-level ``data``.
            tag: Unused tag context.
            tag_dict: Unused captured group mapping.
            result: Mutable mapping receiving shallow copies of selected
                fields.

        Returns:
            The same mapping. Existing result values are replaced for keys
            present on the collection. Missing statement keys leave the result
            unchanged.
        """
        for key in keys:
            if key in transactions.data:
                result[key] = transactions.data[key]
        return result

    return _transactions_to_transaction
