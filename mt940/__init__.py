"""mt940 — parse MT940 bank statement files into rich Python objects.

The high-level entry point is :func:`parse`, which accepts a filename, a file
handle, or raw ``str``/``bytes`` and returns a
:class:`~mt940.models.Transactions` collection you can iterate over. Use
:func:`parse_statements` for files that concatenate several statements, and
:class:`JSONEncoder` to serialize the result to JSON.

Example:
    >>> import mt940
    >>> data = (
    ...     ':20:REF\\n'
    ...     ':25:NL00BANK0123456789\\n'
    ...     ':28C:1/1\\n'
    ...     ':60F:C091019EUR1000,00\\n'
    ...     ':61:0910201020C500,00NTRFNONREF//B\\n'
    ...     ':86:Example transaction\\n'
    ...     ':62F:C091020EUR1500,00\\n'
    ... )
    >>> transactions = mt940.parse(data)
    >>> len(transactions)
    1
    >>> transactions[0].data['amount']
    <500.00 EUR>
"""

from . import json, models, parser, processors, tags, utils
from .__about__ import __version__
from .json import JSONEncoder
from .parser import parse, parse_statements

__all__ = [
    'JSONEncoder',
    '__version__',
    'json',
    'models',
    'parse',
    'parse_statements',
    'parser',
    'processors',
    'tags',
    'utils',
]
