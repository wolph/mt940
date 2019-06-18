# encoding=utf-8
import re
import calendar
import collections


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

# TEST OK: Credit Agricole weak :86: structure, https://firmabank.credit-agricole.pl/mt-front/help/en/10527.html
# TEST OK: Millenium, https://www.bankmillennium.pl/documents/10184/112009/Opis__formatu__pliku_wyciagow__MT940v20120309_1216885.pdf
# TEST OK: BNP PariBas, https://www.bgzbnpparibas.pl/_fileserver/item/1504995 (PL) https://www.bgzbnpparibas.pl/_fileserver/item/1504996 (EN)
# TEST OK: PKO BP, http://www.pkobp.pl/media_files/26455bd3-6edb-417f-9c03-647e27cdc9c5.pdf/ http://www.pkobp.pl/media_files/9ee49e34-754d-451d-83fc-b8a8051f7e33.pdf
# TEST OK: PEKAO SA, ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/PekaoBIZNES24.pdf
# TEST OK FORTIS, ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/Fortis.pdf
# TEST OK Santander (encoding!), (transaction_code 4n) https://static3.santander.pl/asset/P/r/z/Przewodnik-iBiznes24---Formaty-Plikow_91267.pdf
# OK, NOT TESTED: Alior,  ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/Alior.pdf
# OK, NOT TESTED: BPH, ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/BPH_SAM2.pdf
# OK, NOT TESTED: BPH, ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/BPH_SAT.pdf
# OK, NOT TESTED: BPS (Bank Polskiej Spółdzielczości) ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/BPS_MC.pdf
# OK, NOT TESTED: ING, ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/ING.pdf
# OK, NOT TESTED: Krakowski Bank Spółdzielczy, ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/KBS.pdf
# OK, NOT TESTED: https://www.mbank.pl/pdf/firmy/inne/mt940-wyciagi-dzienne-i-miesieczne-w-czesci-detalicznej-mbanku.pdf

# NOT TESTED: DeutscheBank weak :86: structure ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/DeutscheBank.pdf
# NOT TESTED: weak :86: structure ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/GetinNobleBank.PDF
# NOT TESTED: weak :86: structure ftp://ftp.kamsoft.pl/pub/KS-FKW/Pomoce/MT940/BG%C5%BB.pdf

# https://www.db-bankline.deutsche-bank.com/download/MT940_Deutschland_Structure2002.pdf
# DETAIL_KEYS_OLD = {
#     '': 'transaction_code',
#     '00': 'posting_text',
#     '10': 'prima_nota',
#     '20': 'purpose',
#     '30': 'applicant_bin',
#     '31': 'applicant_iban',
#     '32': 'applicant_name',
#     '34': 'return_debit_notes',
#     '35': 'recipient_name',
#     '60': 'additional_purpose',
# }

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
        tmp[segment_type] = segment if not segment_type else segment[2:]
        try:
            segment_type = detail_str[index + 1] + detail_str[index + 2]
        except:
            segment_type = ''
        finally:
            segment = ''

    if segment_type:
        tmp[segment_type] = segment if not segment_type else segment[2:]

    for key, value in tmp.items():
        if key in DETAIL_KEYS:
            result[DETAIL_KEYS[key]] = (result[DETAIL_KEYS[key]] or '') + value.replace('\n', '')


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
    details = tag_dict['transaction_details']
    details = ''.join(detail.strip('\n\r') for detail in details.splitlines())
    details_separator = ''
    if re.match(r'^\d{4}[\?<>~^]\d{2}', details):
    # check for e.g. 103?00... or 103<00
        details_separator = details[4]
    elif re.match(r'^\d{3}[\?<>~^]\d{2}', details):
    # check for e.g. 103?00... or 103<00
        details_separator = details[3]
    elif re.match(r'^[\?<>~^]\d{2}', details):
    # no operation code;check for e.g. ?00... or <00
        details_separator = details[0]
    else:
    # no details separator/unknown separator - only purpose assigned, preserve \n for further analysis as <BR>
        result = dict.fromkeys(DETAIL_KEYS.values())
        result['purpose'] = '<BR>'.join(detail.strip('\n\r') for detail in tag_dict['transaction_details'].splitlines())

    if details_separator != '':
        result.update(_parse_mt940_details(details, details_separator))

        purpose = result.get('purpose')

        if purpose and purpose[:4] in GVC_KEYS:  # pragma: no branch
            result.update(_parse_mt940_gvcodes(result['purpose']))

        del result['transaction_details']

    return result
