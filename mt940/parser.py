# vim: fileencoding=utf-8:
'''

Format
---------------------

Sources:

.. _Swift for corporates: http://www.sepaforcorporates.com/\
    swift-for-corporates/account-statement-mt940-file-format-overview/
.. _Rabobank MT940: https://www.rabobank.nl/images/\
    formaatbeschrijving_swift_bt940s_1_0_nl_rib_29539296.pdf

 - `Swift for corporates`_
 - `Rabobank MT940`_

::

    [] = optional
    ! = fixed length
    a = Text
    x = Alphanumeric, seems more like text actually. Can include special
        characters (slashes) and whitespace as well as letters and numbers
    d = Numeric separated by decimal (usually comma)
    c = Code list value
    n = Numeric
'''

import mt940
from os.path import isfile


def parse(src):
    '''
    Parses mt940 data and returns transactions object

    :param src: file handler to read, filename to read or raw data as string
    :return: Collection of transactions
    :rtype: Transactions
    '''
    if hasattr(src, 'read'):  # pragma: no branch
        data = src.read()
    elif isfile(src):
        src = open(src)
        data = src.read()
    else:
        data = src

    transactions = mt940.models.Transactions()
    transactions.parse(data)
    return transactions
