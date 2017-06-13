# encoding=utf-8
import calendar
import re


def add_currency_pre_processor(currency, overwrite=True):
    def _add_currency_pre_processor(transactions, tag, tag_dict, *args):
        if 'currency' not in tag_dict or overwrite:  # pragma: no branch
            tag_dict['currency'] = currency

        return tag_dict

    return _add_currency_pre_processor


def date_fixup_pre_processor(transactions, tag, tag_dict, *args):
    """
    Replace illegal February 30 dates with the last day of February.

    German banks use a variant of the 30/360 interest rate calculation,
    where each month has always 30 days even February. Python's datetime
    module won't accept such dates.
    """
    if tag_dict['day'] == '30' and tag_dict['month'] == '02':
        year = int(tag_dict['year'], 10)
        tag_dict['day'] = str(calendar.monthrange(year, 2)[1])
        tag_dict['month'] = '02'
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


iph_id_re = re.compile(' ID IPH: X*(?P<iph_id>\d{0,14});')


def mBank_set_iph_id(transactions, tag, tag_dict, *args):
    """
    mBank Collect uses ID IPH to distinguish between virtual accounts,
    adding iph_id may be helpful in further processing
    """
    matches = iph_id_re.search(tag_dict[tag.slug])
    if matches:  # pragma no branch
        tag_dict['iph_id'] = matches.groupdict()['iph_id']
    return tag_dict


tnr_re = re.compile('TNR:[ \n](?P<tnr>\d+\.\d+)', flags=re.MULTILINE)


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


# https://www.db-bankline.deutsche-bank.com/download/MT940_Deutschland_Structure2002.pdf
DETAIL_KEYS = {
    '': 'Geschäftsvorfall-Code',
    '00': 'Buchungstext',
    '10': 'Primanota',
    '20': 'Verwendungszweck',
    '30': 'Auftraggeber BLZ',
    '31': 'Auftraggeber Kontonummer',
    '32': 'Auftraggeber Name',
    '34': 'Rücklastschriften',
    '35': 'Empfänger: Name',
    '60': 'Zusätzl. Verwendungszweckangaben',
}

# https://www.hettwer-beratung.de/sepa-spezialwissen/sepa-technische-anforderungen/sepa-geschäftsvorfallcodes-gvc-mt-940/
GVC_KEYS = {
    '': 'Verwendungszweck',
    'IBAN': 'Auftraggeber IBAN',
    'BIC ': 'Auftraggeber BIC',
    'EREF': 'End to End Referenz',
    'MREF': 'Mandatsreferenz',
    'CRED': 'Auftraggeber Creditor ID',
    'PURP': 'Purpose Code',
    'SVWZ': 'Verwendungszweck',
    'MDAT': 'Mandatsdatum',
    'ABWA': 'Abweichender Auftraggeber',
    'ABWE': 'Abweichender Empfänger',
    'SQTP': 'FRST / ONE / OFF /RECC',
    'ORCR': 'SEPA Mandatsänderung: alte SEPA CI',
    'ORMR': 'SEPA Mandatsänderung: alte SEPA Mandatsreferenz',
    'DDAT': 'SEPA Settlement Tag für R- Message',
    'KREF': 'Kundenreferenz',
    'DEBT': 'Debtor Identifier bei SEPA Überweisung',
    'COAM': 'Compensation Amount',
    'OAMT': 'Original Amount',
}


def _parse_mt940_details(detail_str):
    result = {}
    for key, value in DETAIL_KEYS.items():
        result[value] = None

    tmp = {}
    segment = ''
    segment_type = ''
    for index, char in enumerate(detail_str):
        if char != '?':
            segment += char
            continue
        tmp[segment_type] = segment if not segment_type else segment[2:]
        segment_type = detail_str[index + 1] + detail_str[index + 2]
        segment = ''
    for key, value in tmp.items():
        if key in DETAIL_KEYS:
            result[DETAIL_KEYS[key]] = value
        else:
            if key == '33':
                result[DETAIL_KEYS['32']] += value
            elif key.startswith('2'):
                result[DETAIL_KEYS['20']] += value
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
    if segment_type:
        tmp[segment_type] = text
    else:
        tmp[''] = text
    for key, value in tmp.items():
        result[GVC_KEYS[key]] = value
    return result


def transaction_details_post_processor(transactions, tag, tag_dict, result):
    detail_str = ''.join(
        d.strip() for d in tag_dict['transaction_details'].splitlines())

    result.update(_parse_mt940_details(detail_str))

    if not result['Verwendungszweck']:
        return result

    result.update(_parse_mt940_gvcodes(result['Verwendungszweck']))

    return result
