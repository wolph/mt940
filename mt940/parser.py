"""
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
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import mt940

if TYPE_CHECKING:
    from .models import Transactions


def parse(
    src: Any,
    encoding: str | None = None,
    processors: dict[str, list[Any]] | None = None,
    tags: dict[Any, Any] | None = None,
) -> Transactions:
    """
    Parses mt940 data and returns transactions object

    :param src: file handler to read, filename to read or raw data as string
    :return: Collection of transactions
    :rtype: Transactions
    """

    def safe_is_file(filename: Any) -> bool:
        try:
            return os.path.isfile(filename)
        except ValueError:  # pragma: no cover
            return False

    if hasattr(src, 'read'):  # pragma: no branch
        data = src.read()
    elif safe_is_file(src):
        with open(src, 'rb') as fh:
            data = fh.read()
    else:  # pragma: no cover
        data = src

    if hasattr(data, 'decode'):  # pragma: no branch
        exception = None
        encodings = [encoding, 'utf-8', 'cp852', 'iso8859-15', 'latin1']

        for enc in encodings:  # pragma: no cover
            if not enc:
                continue

            try:
                data = data.decode(enc)
                break
            except UnicodeDecodeError as e:
                exception = e
            except UnicodeEncodeError:
                break
        else:
            assert exception is not None
            raise exception  # pragma: no cover

    assert isinstance(data, str)
    transactions = mt940.models.Transactions(processors, tags)
    transactions.parse(data)

    return transactions
