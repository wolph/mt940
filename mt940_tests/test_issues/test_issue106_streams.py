"""Issue #106: parsing must not depend on sys.stdout/sys.stderr being usable.

Sandboxed / serverless environments (and some GUI apps) run with
``sys.stdout``/``sys.stderr`` set to ``None``. Parsing valid data must work
there without raising ``AttributeError: 'NoneType' object has no attribute
'encoding'``.
"""

import mt940

VALID = """:20:STARTUMS
:25:NL12RABO0123456789
:28C:0
:60F:C220706EUR100,00
:61:2207060706C10,00NTRFref//bank
:86:116?00Payment
:62F:C220706EUR110,00
"""


def test_parses_without_stdout_and_stderr(monkeypatch):
    monkeypatch.setattr('sys.stdout', None)
    monkeypatch.setattr('sys.stderr', None)
    transactions = mt940.parse(VALID)
    assert len(transactions) == 1
    assert str(transactions[0].data['amount']) == '10.00 EUR'
