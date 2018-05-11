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

import os

import mt940


def parse(src, encoding=None):
    '''
    Parses mt940 data and returns transactions object

    :param src: file handler to read, filename to read or raw data as string
    :return: Collection of transactions
    :rtype: Transactions
    '''

    if hasattr(src, 'read'):  # pragma: no branch
        data = src.read()
    elif os.path.isfile(src):
        return parse(open(src, 'rb').read())
    elif hasattr(src, 'decode'):
        exception = None
        encodings = [encoding, 'utf-8', 'cp852', 'iso8859-15', 'latin1']

        for encoding in encodings:  # pragma: no branch
            if not encoding:
                continue

            try:
                data = src.decode(encoding)
                break
            except UnicodeDecodeError as e:
                exception = e
        else:  # pragma: no cover
            raise exception
    else:  # pragma: no cover
        data = src

    transactions = mt940.models.Transactions()
    transactions.parse(data)

    return transactions
