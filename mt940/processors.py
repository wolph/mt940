from __future__ import annotations

import calendar
import collections
import functools
import re
import typing

if typing.TYPE_CHECKING:
    from . import models, tags


def add_currency_pre_processor(
    currency: str, overwrite: bool = True
) -> typing.Callable[..., typing.Any]:
    def _add_currency_pre_processor(
        transactions: models.Transactions,
        tag: tags.Tag,
        tag_dict: dict[str, typing.Any],
        *args: typing.Any,
    ) -> dict[str, typing.Any]:
        if 'currency' not in tag_dict or overwrite:  # pragma: no branch
            tag_dict['currency'] = currency

        return tag_dict

    return _add_currency_pre_processor


def date_fixup_pre_processor(
    transactions: models.Transactions,
    tag: tags.Tag,
    tag_dict: dict[str, typing.Any],
    *args: typing.Any,
) -> dict[str, typing.Any]:
    if tag_dict['month'] == '02':
        year = int(tag_dict['year'], 10)
        _, max_month_day = calendar.monthrange(year, 2)
        if int(tag_dict['day'], 10) > max_month_day:
            tag_dict['day'] = str(max_month_day)

    return tag_dict


def date_cleanup_post_processor(
    transactions: models.Transactions,
    tag: tags.Tag,
    tag_dict: dict[str, typing.Any],
    result: typing.Any,
) -> typing.Any:
    for k in ('day', 'month', 'year', 'entry_day', 'entry_month'):
        result.pop(k, None)

    return result


def mBank_set_transaction_code(
    transactions: models.Transactions,
    tag: tags.Tag,
    tag_dict: dict[str, typing.Any],
    *args: typing.Any,
) -> dict[str, typing.Any]:
    """
    mBank Collect uses transaction code 911 to distinguish incoming mass
    payments transactions, adding transaction_code may be helpful in further
    processing
    """
    tag_value = tag_dict[tag.slug]
    tag_dict['transaction_code'] = int(
        tag_value.split(';')[0].split(' ', 1)[0]
    )

    return tag_dict


iph_id_re = re.compile(r' ID IPH: X*(?P<iph_id>\d{0,14});')


def mBank_set_iph_id(
    transactions: models.Transactions,
    tag: tags.Tag,
    tag_dict: dict[str, typing.Any],
    *args: typing.Any,
) -> dict[str, typing.Any]:
    """
    mBank Collect uses ID IPH to distinguish between virtual accounts,
    adding iph_id may be helpful in further processing
    """
    matches = iph_id_re.search(tag_dict[tag.slug])

    if matches:  # pragma: no branch
        tag_dict['iph_id'] = matches.groupdict()['iph_id']

    return tag_dict


tnr_re = re.compile(
    r'TNR:[ \n](?P<tnr>\d+\.\d+)', flags=re.MULTILINE | re.UNICODE
)


def mBank_set_tnr(
    transactions: models.Transactions,
    tag: tags.Tag,
    tag_dict: dict[str, typing.Any],
    *args: typing.Any,
) -> dict[str, typing.Any]:
    """
    mBank Collect states TNR in transaction details as unique id for
    transactions, that may be used to identify the same transactions in
    different statement files eg. partial mt942 and full mt940
    Information about tnr uniqueness has been obtained from mBank support,
    it lacks in mt940 mBank specification.
    """

    matches = tnr_re.search(tag_dict[tag.slug])

    if matches:  # pragma: no branch
        tag_dict['tnr'] = matches.groupdict()['tnr']

    return tag_dict


# https://www.db-bankline.deutsche-bank.com/download/MT940_Deutschland_Structure2002.pdf
DETAIL_KEYS = {
    '': 'transaction_code',
    '00': 'posting_text',
    '10': 'prima_nota',
    '20': 'purpose',
    '30': 'applicant_bin',
    '31': 'applicant_iban',
    '32': 'applicant_name',
    '34': 'return_debit_notes',
    '35': 'recipient_name',
    '60': 'additional_purpose',
}

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


def _parse_mt940_details(
    detail_str: str, space: bool = False
) -> dict[str, typing.Any]:
    tmp = _parse_segments(detail_str)
    result = _process_segments(tmp)
    return _join_result(result, space)


def _parse_segments(detail_str: str) -> collections.OrderedDict[str, str]:
    tmp = collections.OrderedDict()
    segment = ''
    segment_type = ''

    for index, char in enumerate(detail_str):
        if char != '?':
            segment += char
            continue

        if index + 2 >= len(detail_str):
            break

        tmp[segment_type] = segment if not segment_type else segment[2:]
        segment_type = detail_str[index + 1] + detail_str[index + 2]
        segment = ''

    if segment_type:  # pragma: no branch
        tmp[segment_type] = segment if not segment_type else segment[2:]

    return tmp


def _process_segments(
    tmp: collections.OrderedDict[str, str],
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = collections.defaultdict(list)
    for key, value in tmp.items():
        if key in DETAIL_KEYS:
            result[DETAIL_KEYS[key]].append(value)
        elif key == '33':
            key32 = DETAIL_KEYS['32']
            result[key32].append(value)
        elif key.startswith('2'):
            key20 = DETAIL_KEYS['20']
            result[key20].append(value)
        elif key in {'60', '61', '62', '63', '64', '65'}:
            key60 = DETAIL_KEYS['60']
            result[key60].append(value)
    return result


def _join_result(
    result: dict[str, list[str]], space: bool
) -> dict[str, typing.Any]:
    joined_result = {}
    for key in DETAIL_KEYS.values():
        if space:
            value = ' '.join(result[key])
        else:
            value = ''.join(result[key])

        joined_result[key] = value or None
    return joined_result


def _parse_mt940_gvcodes(purpose: str) -> dict[str, typing.Any]:
    result: dict[str, typing.Any] = {}

    for value in GVC_KEYS.values():
        result[value] = None

    tmp: dict[str, str] = {}
    segment_type: str | None = None
    text = ''

    for index, char in enumerate(purpose):
        if char == '+' and purpose[index - 4 : index] in GVC_KEYS:
            if segment_type:
                tmp[segment_type] = text[:-4]
                text = ''
            else:
                text = ''
            segment_type = purpose[index - 4 : index]
        else:
            text += char

    if segment_type:  # pragma: no branch
        tmp[segment_type] = text
    else:
        tmp[''] = text  # pragma: no cover

    for key, value in tmp.items():
        result[GVC_KEYS[key]] = value

    return result


def transaction_details_post_processor(
    transactions: models.Transactions,
    tag: tags.Tag,
    tag_dict: dict[str, typing.Any],
    result: dict[str, typing.Any],
    space: bool = False,
) -> dict[str, typing.Any]:
    """Parse the extra details in some transaction formats such as the 60-65
    keys.

    Args:
        transactions: list of transactions
        tag: tag
        tag_dict: dict with the raw tag details
        result: the resulting tag dict
        space: include spaces between lines in the mt940 details
    """
    details = tag_dict['transaction_details']
    details = ''.join(detail.strip('\n\r') for detail in details.splitlines())

    # check for e.g. 103?00...
    if re.match(r'^\d{3}\?\d{2}', details):
        result.update(_parse_mt940_details(details, space=space))

        purpose = result.get('purpose')

        if purpose and any(
            gvk in purpose for gvk in GVC_KEYS if gvk != ''
        ):  # pragma: no branch
            result.update(_parse_mt940_gvcodes(result['purpose']))

        del result['transaction_details']

    return result


transaction_details_post_processor_with_space = functools.partial(
    transaction_details_post_processor, space=True
)


def transactions_to_transaction(*keys: str):
    """Copy the global transactions details to the transaction.

    Args:
        *keys (str): the keys to copy to the transaction
    """

    def _transactions_to_transaction(
        transactions: models.Transactions,
        tag: tags.Tag,
        tag_dict: dict[str, typing.Any],
        result: dict[str, typing.Any],
    ) -> dict[str, typing.Any]:
        """Copy the global transactions details to the transaction.

        Args:
            transactions (mt940.models.Transactions): list of transactions
            tag (mt940.tags.Tag): tag
            tag_dict (dict): dict with the raw tag details
            result (dict): the resulting tag dict
        """
        for key in keys:
            if key in transactions.data:
                result[key] = transactions.data[key]

        return result

    return _transactions_to_transaction
