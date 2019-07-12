# encoding=utf-8
import calendar
import collections
import re


def add_currency_pre_processor(currency, overwrite=True):
    def _add_currency_pre_processor(transactions, tag, tag_dict, *args):
        if 'currency' not in tag_dict or overwrite:  # pragma: no branch
            tag_dict['currency'] = currency

        return tag_dict

    return _add_currency_pre_processor


def date_fixup_pre_processor(transactions, tag, tag_dict, *args):
    """
    Replace illegal February 29, 30 dates with the last day of February.

    German banks use a variant of the 30/360 interest rate calculation,
    where each month has always 30 days even February. Python's datetime
    module won't accept such dates.
    """
    if tag_dict['month'] == '02':
        year = int(tag_dict['year'], 10)
        _, max_month_day = calendar.monthrange(year, 2)
        if int(tag_dict['day'], 10) > max_month_day:
            tag_dict['day'] = str(max_month_day)

    return tag_dict


def date_cleanup_post_processor(transactions, tag, tag_dict, result):
    for k in ('day', 'month', 'year', 'entry_day', 'entry_month'):
        result.pop(k, None)

    return result


def mBank_set_transaction_code(transactions, tag, tag_dict, *args):
    """
    mBank Collect uses transaction code 911 to distinguish icoming mass
    payments transactions, adding transaction_code may be helpful in further
    processing
    """
    tag_dict['transaction_code'] = int(
        tag_dict[tag.slug].split(';')[0].split(' ', 1)[0])

    return tag_dict


iph_id_re = re.compile(r' ID IPH: X*(?P<iph_id>\d{0,14});')


def mBank_set_iph_id(transactions, tag, tag_dict, *args):
    """
    mBank Collect uses ID IPH to distinguish between virtual accounts,
    adding iph_id may be helpful in further processing
    """
    matches = iph_id_re.search(tag_dict[tag.slug])

    if matches:  # pragma no branch
        tag_dict['iph_id'] = matches.groupdict()['iph_id']

    return tag_dict


tnr_re = re.compile(r'TNR:[ \n](?P<tnr>\d+\.\d+)',
                    flags=re.MULTILINE | re.UNICODE)


def mBank_set_tnr(transactions, tag, tag_dict, *args):
    """
    mBank Collect states TNR in transaction details as unique id for
    transactions, that may be used to identify the same transactions in
    different statement files eg. partial mt942 and full mt940
    Information about tnr uniqueness has been obtained from mBank support,
    it lacks in mt940 mBank specification.
    """

    matches = tnr_re.search(tag_dict[tag.slug])

    if matches:  # pragma no branch
        tag_dict['tnr'] = matches.groupdict()['tnr']

    return tag_dict

DETAIL_KEYS = {
    '': 'transaction_code',
    '00': 'posting_text',
    '10': 'prima_nota',
    '20': 'purpose',
    '21': 'purpose',
    '22': 'purpose',
    '23': 'purpose',
    '24': 'purpose',
    '25': 'purpose',
    '26': 'purpose',
    '27': 'applicant',
    '28': 'applicant',
    '29': 'applicant',
    '30': 'applicant_bin',
    '31': 'applicant_iban',
    '32': 'applicant_name',
    '33': 'applicant_name',
    '34': 'return_debit_notes',
    '35': 'recipient_name',
    '38': 'applicant_iban_full',
    '60': 'applicant',
    '61': 'additional_purpose',
    '62': 'additional_purpose',
    '63': 'bank_reference',
    '64': 'additional_purpose',
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


def _parse_mt940_details(detail_str, details_separator):
    result = dict.fromkeys(DETAIL_KEYS.values())

    tmp = collections.OrderedDict()
    segment = ''
    segment_type = ''

    for index, char in enumerate(detail_str):
        if char != details_separator:
            segment += char
            continue

        if index + 2 >= len(detail_str):
            break

        tmp[segment_type] = segment if not segment_type else segment[2:]
        segment_type = detail_str[index + 1] + detail_str[index + 2]
        segment = ''

    if segment_type:
        tmp[segment_type] = segment if not segment_type else segment[2:]

    for key, value in tmp.items():
        if key in DETAIL_KEYS:
            result[DETAIL_KEYS[key]] += value.replace('\n', '')

    return result


def _parse_mt940_gvcodes(purpose):
    result = {}

    for key, value in GVC_KEYS.items():
        result[value] = None

    tmp = {}
    segment_type = None
    text = ''

    for index, char in enumerate(purpose):
        if char == '+' and purpose[index - 4:index] in GVC_KEYS:
            if segment_type:
                tmp[segment_type] = text[:-4]
                text = ''
            else:
                text = ''
            segment_type = purpose[index - 4:index]
        else:
            text += char

    if segment_type:  # pragma: no branch
        tmp[segment_type] = text
    else:
        tmp[''] = text  # pragma: no cover

    for key, value in tmp.items():
        result[GVC_KEYS[key]] = value

    return result


def transaction_details_post_processor(transactions, tag, tag_dict, result):
    raw_details = tag_dict['transaction_details'].splitlines()
    details = ''.join(detail.strip('\n\r') for detail in raw_details)
    details_separator = ''
    if re.match(r'^\d{4}[?<>~^]\d{2}', details):
        # check for e.g. 103?00... or 103<00
        details_separator = details[4]
    elif re.match(r'^\d{3}[?<>~^]\d{2}', details):
        # check for e.g. 103?00... or 103<00
        details_separator = details[3]
    elif re.match(r'^[?<>~^]\d{2}', details):
        # no operation code;check for e.g. ?00... or <00
        details_separator = details[0]
    else:
        # no details separator/unknown separator - only purpose assigned,
        # preserve \n for further analysis as <BR>
        result = dict.fromkeys(DETAIL_KEYS.values())
        result['purpose'] = '<BR>'.join(d.strip('\n\r') for d in raw_details)

    if details_separator != '':
        result.update(_parse_mt940_details(details, details_separator))

        purpose = result.get('purpose')

        if purpose and purpose[:4] in GVC_KEYS:  # pragma: no branch
            result.update(_parse_mt940_gvcodes(result['purpose']))

        del result['transaction_details']

    return result
