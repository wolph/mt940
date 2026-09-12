# MT940

[![CI](https://github.com/WoLpH/mt940/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/WoLpH/mt940/actions/workflows/ci.yml?query=branch%3Amaster)
[![PyPI](https://img.shields.io/pypi/v/mt-940)](https://pypi.org/project/mt-940/)
[![Python](https://img.shields.io/pypi/pyversions/mt-940)](https://pypi.org/project/mt-940/)
[![Documentation](https://readthedocs.org/projects/mt940/badge/?version=latest)](https://mt940.readthedocs.io/)
[![Coverage](https://coveralls.io/repos/github/wolph/mt940/badge.svg?branch=master)](https://coveralls.io/github/wolph/mt940?branch=master)

Parse MT940 bank statements into Python transactions, decimal amounts, dates
and balances. The `mt-940` distribution imports as `mt940`, supports Python
3.10 through 3.15 and has no runtime dependencies. Type information ships in the
package through `py.typed`.

## Parse your first statement

Install the package in your project's environment:

```console
uv pip install mt-940
```

This complete example uses a fictional account. Paste it into Python:

```python
import mt940

source: str = """:20:EXAMPLE-001
:25:EXAMPLE-ACCOUNT
:28C:1/1
:60F:C260101EUR100,00
:61:2601020102D12,50NTRFCOFFEE//BANK-001
:86:Coffee supplies
:62F:C260102EUR87,50
"""
statement: mt940.models.Transactions = mt940.parse(source)
transaction: mt940.models.Transaction = statement[0]
print(transaction.data['date'], transaction.data['amount'])
print(statement.data['final_closing_balance'])
```

The test suite executes that code. Its output is:

```text
2026-01-02 -12.50 EUR
87.50 EUR @ 2026-01-02
```

The debit mark `D` produces a negative `Decimal`. The closing balance comes
from `:62F:` in the input. Parsing does not calculate or reconcile balances.
Transaction fields live in `transaction.data`, and statement metadata lives
in `statement.data`. A missing source field can be absent or `None`, depending
on its tag and processors.

## Choose the input and output you need

- Pass a `pathlib.Path` for a file. A missing `Path` raises `FileNotFoundError`.
  Plain strings naming no existing file are interpreted as statement text.
- Pass raw `str` or `bytes`, or an open text or binary stream. Streams are read
  from their current position and remain open. Numeric file descriptors close
  after reading.
- Use `mt940.parse_statements(source)` for separate `:20:` statement blocks.
  `mt940.parse(source)` merges transactions and keeps the last value for each
  statement metadata key. `:28C:` page numbers do not split statements.
- Use `json.dumps(statement, cls=mt940.JSONEncoder)` to export metadata and
  transactions. Decimal values become strings. There is no matching decoder
  that reconstructs the models.

The [usage guide](https://mt940.readthedocs.io/en/latest/usage.html) explains
these choices. The [API reference](https://mt940.readthedocs.io/en/latest/modules.html)
covers tags, processors, models and parser helpers.

## Bank formats and compatibility

Built-in tags cover references (`20`, `21`), account and sequence information
(`25`, `28C`), time (`13D`), floor limits (`34F`), balances (`60`, `62`, `64`,
`65`), transactions (`61`), details (`86`), summaries (`90C`, `90D`) and
non-SWIFT extensions (`NS`). Bank-specific fixtures are regression evidence
for those files. They do not guarantee every export from a named bank.

Custom tag instances and ordered pre/post processors can adapt a collection.
`StatementASNB` and `StatementGLS` are explicit alternatives for their `:61:`
variants. Processor overrides replace a whole slot. Copy its default list
when adding a callback.

Ten `mt940.Options` switches preserve legacy output unless enabled. All default
to `False`. `mt940.Options(reversal_sign=True)` changes the sign of `RC`
transactions, and `mt940.Options.all()` enables every declared switch.
The [Options reference](https://mt940.readthedocs.io/en/latest/mt940.options.html)
documents each effect. Compare outputs for your bank before changing options.

## Develop and contribute

Clone `develop`. `master` tracks stable releases. Development and documentation
tools use Python 3.12, while the library supports Python 3.10 through 3.15:

```console
git clone --branch develop https://github.com/WoLpH/mt940.git
cd mt940
uv sync --python 3.12
uv run lefthook install
uv run tox
```

The checks include the Python test matrix and combined coverage, five type
checkers (mypy, basedpyright, pyright, pyrefly and ty), Ruff, documentation,
spelling, repository configuration, workflow security and dependency audits.
See [CONTRIBUTING.rst](https://github.com/WoLpH/mt940/blob/develop/CONTRIBUTING.rst)
for focused commands and fixture requirements. The runnable `examples/`
package uses fictional data and includes recorded outputs checked by pytest.

## Support

mt940 is maintained by [Rick van Hattem](https://github.com/wolph) in his own time. Most of that time goes on bank statement dialects, because every bank reads the spec slightly differently.

If it saved you an afternoon, a tip covers an hour of issue triage:
[Ko-fi](https://ko-fi.com/wolph_gh) or [GitHub Sponsors](https://github.com/sponsors/wolph).

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/wolph_gh)

[Documentation](https://mt940.readthedocs.io/) |
[Source](https://github.com/WoLpH/mt940) |
[Issues](https://github.com/WoLpH/mt940/issues) |
[Releases](https://github.com/WoLpH/mt940/releases) |
[BSD-3-Clause licence](https://github.com/WoLpH/mt940/blob/master/LICENSE)
