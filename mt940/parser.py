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


def parse(fh):
    '''
    Parses mt940 data and returns transactions object

    :param file or str fh: file handler or filename to read
    :return: Collection of transactions
    :rtype: Transactions
    '''
    if not hasattr(fh, 'read'):  # pragma: no branch
        fh = open(fh)
    data = fh.read()

    transactions = mt940.models.Transactions()
    transactions.parse(data)
    return transactions

