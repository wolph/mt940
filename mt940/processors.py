import calendar


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



