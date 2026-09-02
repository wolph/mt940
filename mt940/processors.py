# pyright: reportUnusedParameter=false
# Every processor shares one positional signature, so most of them leave at
# least one of the arguments untouched.
"""Pre- and post-processors that adjust parsed tag data.

This module contains pre- and post-processors for modifying tag
dictionaries in MT940 processing. It provides functions for currency
addition, date fix-up, transaction code extraction, transaction details
parsing, and segment joining for transaction details.
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
    """Return a pre-processor that adds currency information to tag data.

    Args:
        currency: The currency to set in the tag dictionary.
        overwrite: Whether to overwrite existing currency information.

    Returns:
        A pre-processor function that adds currency information.
    """

    def _add_currency_pre_processor(
        transactions: models.Transactions,
        tag: tags.Tag,
        tag_dict: dict[str, Any],
        *args: Any,
    ) -> dict[str, Any]:
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
    """Adjust the date in the tag dictionary if necessary.

    If the day in February exceeds the maximum day in that month,
    adjust it to the last day of February.

    Args:
        transactions: The transactions object.
        tag: The tag being processed.
        tag_dict: The tag dictionary.
        *args: Ignored, present so every processor shares one signature.

    Returns:
        The adjusted tag dictionary.
    """
    # If the month is February, ensure that the day does not exceed the
    # maximum valid day.
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
    """Remove date components from the result dictionary.

    Removes the 'day', 'month', 'year', 'entry_day', and 'entry_month' keys
    from the result dictionary.

    Args:
        transactions: The transactions object.
        tag: The tag being processed.
        tag_dict: The tag dictionary.
        result: The result dictionary.

    Returns:
        The adjusted result dictionary.
    """
    # Remove all date-related keys from the result dictionary.
    for k in ('day', 'month', 'year', 'entry_day', 'entry_month'):
        result.pop(k, None)
    return result


def mBank_set_transaction_code(
    transactions: models.Transactions,
    tag: tags.Tag,
    tag_dict: dict[str, Any],
    *args: Any,
) -> dict[str, Any]:
    """Set ``transaction_code`` from an mBank Collect tag value.

    mBank Collect uses transaction code 911 to distinguish incoming mass
    payment transactions, so exposing the code helps further processing.

    Args:
        transactions: The transactions object.
        tag: The tag being processed.
        tag_dict: The tag dictionary.
        *args: Ignored, present so every processor shares one signature.

    Returns:
        The tag dictionary with ``transaction_code`` added.
    """
    # Extract the transaction code from the tag value.
    # Split the value at ';' and then by the first space to isolate the
    # numeric transaction code, which is converted to an integer before
    # being assigned.
    tag_value = tag_dict[tag.slug]
    tag_dict['transaction_code'] = int(
        tag_value.split(';')[0].split(' ', 1)[0]
    )
    return tag_dict


# Regular expression to extract IPH ID from mBank tag values.
iph_id_re = re.compile(r' ID IPH: X*(?P<iph_id>\d{0,14});')


def mBank_set_iph_id(
    transactions: models.Transactions,
    tag: tags.Tag,
    tag_dict: dict[str, Any],
    *args: Any,
) -> dict[str, Any]:
    """Set ``iph_id`` from an mBank Collect tag value.

    mBank Collect uses the IPH ID to distinguish between virtual accounts,
    so exposing it helps further processing.

    Args:
        transactions: The transactions object.
        tag: The tag being processed.
        tag_dict: The tag dictionary.
        *args: Ignored, present so every processor shares one signature.

    Returns:
        The tag dictionary, with ``iph_id`` added when the value carries one.
    """
    matches = iph_id_re.search(tag_dict[tag.slug])
    if matches:
        tag_dict['iph_id'] = matches.group('iph_id')
    return tag_dict


# Regular expression to extract the Transaction Number (TNR) from tag
# values, accounting for potential newline characters.
tnr_re = re.compile(r'TNR:[ \n](?P<tnr>\d+\.\d+)', flags=re.MULTILINE)


def mBank_set_tnr(
    transactions: models.Transactions,
    tag: tags.Tag,
    tag_dict: dict[str, Any],
    *args: Any,
) -> dict[str, Any]:
    """Set ``tnr`` from an mBank Collect tag value.

    mBank Collect states the TNR in the transaction details as a unique id,
    which identifies the same transaction across statement files, such as a
    partial MT942 and the full MT940. mBank support confirmed the uniqueness,
    the mBank MT940 specification does not mention it.

    Args:
        transactions: The transactions object.
        tag: The tag being processed.
        tag_dict: The tag dictionary.
        *args: Ignored, present so every processor shares one signature.

    Returns:
        The tag dictionary, with ``tnr`` added when the value carries one.
    """
    matches = tnr_re.search(tag_dict[tag.slug])
    if matches:
        tag_dict['tnr'] = matches.group('tnr')
    return tag_dict


# https://www.db-bankline.deutsche-bank.com/download/MT940_Deutschland_Structure2002.pdf
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

# https://www.hettwer-beratung.de/sepa-spezialwissen/sepa-technische-anforderungen/sepa-gesch%C3%A4ftsvorfallcodes-gvc-mt-940/
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
    """Parse segments from a detail string.

    This function splits the provided detail string into segments using
    the '?' delimiter. Each segment is associated with a two-character
    segment type that follows the '?' marker.

    Args:
        detail_str: A string containing the transaction detail segments.

    Returns:
        An OrderedDict mapping segment identifiers to their extracted content.
    """
    tmp: collections.OrderedDict[str, str] = collections.OrderedDict()
    segment = ''
    segment_type = ''

    for index, char in enumerate(detail_str):
        if char != '?':
            # Accumulate characters into the current segment until a '?'
            # delimiter is encountered.
            segment += char
            continue

        # If there aren't enough characters left to form a segment type,
        # exit the loop.
        if index + 2 >= len(detail_str):
            break

        # Finalize the current segment. If a segment type exists, skip the
        # first two header characters.
        tmp[segment_type] = segment if not segment_type else segment[2:]
        # Extract the new segment type from the following two characters.
        segment_type = detail_str[index + 1] + detail_str[index + 2]
        # Reset the segment accumulator for the next segment.
        segment = ''

    if segment_type:
        # Finalize the last captured segment.
        tmp[segment_type] = segment if not segment_type else segment[2:]

    return tmp


def _process_segments(
    tmp: collections.OrderedDict[str, str],
    detail_keys: dict[str, str] = DETAIL_KEYS,
) -> dict[str, list[str]]:
    """Process segments into result dictionary.

    Args:
        tmp: An OrderedDict of segment types to their content.
        detail_keys: The sub-field to key mapping, :data:`DETAIL_KEYS` or
            :data:`DETAIL_KEYS_APPLICANT_IBAN`.

    Returns:
        A dictionary mapping keys to lists of segment contents.
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
            # the end of a detail segment (issue #109); strip the dangling
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
    """Join result lists into strings.

    Args:
        result: The result dictionary with lists of strings.
        space: Whether to include spaces between segments.
        detail_keys: The mapping whose keys the result must all carry.

    Returns:
        A dictionary with joined strings.
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
    """Parse MT940 transaction details.

    Args:
        detail_str: The detail string to parse.
        space: Whether to include spaces between segments.
        detail_keys: The sub-field to key mapping, :data:`DETAIL_KEYS` or
            :data:`DETAIL_KEYS_APPLICANT_IBAN`.

    Returns:
        A dictionary of parsed transaction details.
    """
    tmp = _parse_segments(detail_str)
    result = _process_segments(tmp, detail_keys)
    return _join_result(result, space, detail_keys)


def _parse_mt940_gvcodes(
    purpose: str,
    *,
    keep_leading_text: bool = False,
) -> dict[str, str | None]:
    """Parse MT940 GVC codes from the purpose string.

    Args:
        purpose: The purpose string to parse.
        keep_leading_text: Refuse to treat a ``+`` within the first four
            characters as the end of a GVC keyword, so free text in front of
            the first keyword survives. Off, 5.0.0 dropped that text.

    Returns:
        A dictionary of parsed GVC codes.
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
                # If already processing a segment, finalize it by removing
                # the trailing GVC key and reset the text accumulator.
                tmp[segment_type] = text[:-_GVC_KEY_LENGTH]
                text = ''
            else:
                text = ''
            # Set the new segment type from the four characters preceding
            # the '+'.
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
    """Parse the structured ``:86:`` details, including the 60-65 keys.

    Args:
        transactions: The transactions object.
        tag: The tag being processed.
        tag_dict: The tag dictionary.
        result: The result dictionary.
        space: Whether to include spaces between segments.

    Returns:
        The updated result dictionary.
    """
    options = _options_of(transactions)
    detail_keys = (
        DETAIL_KEYS_APPLICANT_IBAN if options.applicant_iban else DETAIL_KEYS
    )
    details = tag_dict['transaction_details']
    details = ''.join(detail.strip('\n\r') for detail in details.splitlines())

    # check for e.g. 103?00...
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

        # Clean up the purpose field
        if result.get('purpose'):
            # Remove trailing "BIC" without an actual BIC value
            result['purpose'] = result['purpose'].removesuffix(' BIC')

        del result['transaction_details']

    return result


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
    """Copy the global transactions details to the transaction.

    Args:
        *keys: The keys to copy to the transaction.

    Returns:
        A post-processor function that copies specified keys.
    """

    def _transactions_to_transaction(
        transactions: models.Transactions,
        tag: tags.Tag,
        tag_dict: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Copy the global transactions details to the transaction.

        Args:
            transactions: The transactions object.
            tag: The tag being processed.
            tag_dict: The tag dictionary.
            result: The result dictionary.

        Returns:
            The updated result dictionary.
        """
        # Copy each specified key from the global transactions data to the
        # transaction-specific dictionary.
        for key in keys:
            if key in transactions.data:
                result[key] = transactions.data[key]
        return result

    return _transactions_to_transaction
