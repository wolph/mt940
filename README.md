# MT940

[![CI](https://github.com/WoLpH/mt940/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/WoLpH/mt940/actions/workflows/ci.yml?query=branch%3Amaster)
[![PyPI](https://img.shields.io/pypi/v/mt-940)](https://pypi.org/project/mt-940/)
[![Python](https://img.shields.io/pypi/pyversions/mt-940)](https://pypi.org/project/mt-940/)
[![Downloads](https://img.shields.io/pypi/dm/mt-940)](https://pypi.org/project/mt-940/)
[![Documentation](https://readthedocs.org/projects/mt940/badge/?version=latest)](https://mt940.readthedocs.io/)
[![Coverage](https://coveralls.io/repos/github/WoLpH/mt940/badge.svg?branch=develop)](https://coveralls.io/github/WoLpH/mt940?branch=develop)
[![License](https://img.shields.io/pypi/l/mt-940)](https://github.com/WoLpH/mt940/blob/develop/LICENSE)

`mt940` parses **MT940 bank statement files** into smart, fully typed Python
collections you can iterate, aggregate and serialize. It has no runtime
dependencies, ships type information (`py.typed`), and copes with the quirks of
many real-world banks.

```python
import mt940

transactions = mt940.parse('statement.sta')
for transaction in transactions:
    print(transaction.data['date'], transaction.data['amount'])
```

## Why mt940

- **Zero runtime dependencies**: pure standard library.
- **Fully typed**: ships `py.typed` and is checked under mypy, basedpyright, pyrefly and ty.
- **Battle-tested**: 100% test coverage against fixtures from many banks.
- **Smart models**: amounts, balances and dates come back as rich Python
  objects, not raw strings.
- **JSON-ready**: a single encoder serializes a whole statement.
- **Extensible**: opt-in tags and pre/post processors for bank-specific
  formats.
- **Modern Python**: supports 3.10 through 3.14.

## Installation

```bash
pip install mt-940
```

Using [uv](https://docs.astral.sh/uv/):

```bash
uv add mt-940
```

Requires Python 3.10 or newer.

## Quick start

`parse()` accepts a filename, an open file handle, or the raw `str`/`bytes`
contents, and returns a `Transactions` collection:

```python
import mt940
import pprint

transactions = mt940.parse('mt940_tests/jejik/abnamro.sta')

# Statement-level data (balances, account, ...) lives on the collection:
pprint.pprint(transactions.data)

# Iterate the individual transactions:
for transaction in transactions:
    print(transaction.data['date'], transaction.data['amount'])
    pprint.pprint(transaction.data)
```

Each `Transaction` exposes a `data` dictionary with the parsed fields. Which
fields are present depends on the source bank and the tags in the file.

## Usage

### Reading balances

Statement-level balances live on the `Transactions` object's `data`, not on the
individual transactions. This works even for files with no transactions at all:

```python
import mt940

transactions = mt940.parse('statement.sta')
print(transactions.data['final_opening_balance'])
print(transactions.data['final_closing_balance'])
print(transactions.data['available_balance'])
```

### Set opening / closing balance on each transaction

```python
import mt940
import pprint

mt940.tags.BalanceBase.scope = mt940.models.Transaction

# The currency has to be set manually when moving the BalanceBase scope to
# Transaction.
transactions = mt940.models.Transactions(
    processors=dict(
        pre_statement=[mt940.processors.add_currency_pre_processor('EUR')],
    )
)

with open('mt940_tests/jejik/abnamro.sta') as fh:
    transactions.parse(fh.read())

for transaction in transactions:
    pprint.pprint(transaction.data)
```

### Multiple statements in one file

A single `parse()` merges everything into one `Transactions` and keeps only the
**last** block's statement-level data (e.g. balances). For files that
concatenate several statements (including balance-only blocks), use
`parse_statements()`, which splits on `:20:` boundaries and returns one
`Transactions` per statement, each with its own balances:

```python
import mt940

# src may be a filename, a file handle or the raw data, just like parse()
for statement in mt940.parse_statements('statements.sta'):
    print(statement.data['final_opening_balance'])
    print(statement.data['final_closing_balance'])
```

### Serializing to JSON

```python
import json
import mt940

transactions = mt940.parse('statement.sta')
print(json.dumps(transactions, indent=4, cls=mt940.JSONEncoder))
```

### Transaction grouping (opt-in)

By default a new transaction is started only on the `:61:` statement tag. Some
banks delimit transactions differently, for example by repeating the `:20:`
transaction reference per block. Because changing the default grouping would
break existing users, this behaviour is **opt-in**: pass `transaction_boundary`
(an iterable of tag *slugs*) to start a new transaction on those tags too.

```python
import mt940

# Each `:20:` (transaction_reference_number) starts its own transaction:
transactions = mt940.parse(
    'statement.sta', transaction_boundary={'transaction_reference_number'}
)
```

The same option is accepted by
`mt940.models.Transactions(transaction_boundary=...)`.

### Banks with longer reference fields (opt-in)

Some banks (e.g. GLS / Atruvia) put a customer reference longer than the SWIFT
16-character cap on the `:61:` line, followed by the `//` bank reference.
Relaxing the default would change how other banks (e.g. Rabobank) split
same-line data, so this is handled by an **opt-in** `StatementGLS` tag:

```python
import mt940

gls = mt940.tags.StatementGLS()
transactions = mt940.parse('statement.sta', tags={gls.id: gls})
```

(Longer *supplementary details*, issue #117, e.g. Wise, are handled by the
default parser and need no opt-in.)

### Statements from the Dutch bank ASN (opt-in)

Tag 61 in ASN statements does not follow the SWIFT specification, so the opt-in
`StatementASNB` tag is used:

```python
import mt940
import pprint

tag = mt940.tags.StatementASNB()
transactions = mt940.models.Transactions(tags={tag.id: tag})

with open('mt940_tests/ASNB/mt940.txt') as fh:
    transactions.parse(fh.read())

pprint.pprint(transactions.data, sort_dicts=False)
```

### Parser fixes (opt-in)

Several parsing fixes change the output for input that 5.0.0 accepted without
complaint. Because that would break existing users, every one of them is off
by default and switched on through `mt940.Options`. The next major release
turns them all on.

```python
import mt940

options = mt940.Options(reversal_sign=True, applicant_iban=True)
transactions = mt940.parse(
    'mt940_tests/betterplace/sepa_mt9401.sta', options=options
)

# Or take every fix at once, which is what the next major release does.
transactions = mt940.parse('statement.sta', options=mt940.Options.all())
```

| Option | Default (5.0.0) | Switched on |
|---|---|---|
| `applicant_iban` | `?31` is prepended to `applicant_name` | `?31` is `applicant_iban` (issue #132, the 4.x behaviour) |
| `merge_keeps_values` | a structured `:86:` overwrites other tags' values with `None` for sub-fields it lacks | existing values survive, so the `:61:` customer reference keeps its value |
| `reversal_sign` | the `RC` reversal mark gives a positive amount | `RC` is negative like the debit it is (issue #130) |
| `case_insensitive_marks` | a lowercase `d` or `rc` mark does not sign the amount | lowercase marks work like uppercase ones |
| `timezone_offset` | a `:13D:` offset of `+0100` is read as 100 minutes | `+0100` is one hour |
| `unbounded_details` | `:86:` details are cut after nine chunks of 65 characters | details of any length are kept |
| `non_swift_free_text` | an `:NS:` line without a two-digit sub-tag loses its content | the content is kept |
| `floor_limit_blank_mark` | a blank `:34F:` mark yields a key with a leading space and no currency | it yields both floor limits and the currency |
| `strip_bom` | a leading byte-order mark hides the first `:20:` tag | the mark is dropped |
| `gvc_leading_text` | free text before the first GVC keyword is lost when it contains a `+` | the text is kept |

Crash fixes need no option: input that made 5.0.0 raise now parses in every
mode.

## Supported tags

| Tag | Meaning |
| --- | --- |
| `:13:` | Date/time the report was created |
| `:20:` | Transaction reference number |
| `:21:` | Related reference |
| `:25:` | Account identification |
| `:28C:` | Statement number / sequence number |
| `:34F:` | Floor limit for debit and credit |
| `:60F:` / `:60M:` | (Final / intermediate) opening balance |
| `:61:` | Statement line (a transaction) |
| `:62F:` / `:62M:` | (Final / intermediate) closing balance |
| `:64:` | Available balance |
| `:65:` | Forward available balance |
| `:86:` | Transaction details |
| `:90C:` / `:90D:` | Number and sum of credit / debit entries |
| `:NS:` | Bank-specific non-SWIFT extensions |

## Contributing

Help is greatly appreciated. Please clone the **develop** branch and run `tox`
before opening a pull request. CI runs the same tox environments: ruff with
every rule enabled, four type checkers (mypy, basedpyright, pyrefly and ty),
the test suite on Python 3.10 through 3.14 with 100% coverage required, the
documentation build, and audits of the TOML files, the workflows and the
dependencies.

```bash
git clone --branch develop https://github.com/WoLpH/mt940.git
cd mt940
uv sync
uv run lefthook install  # ruff on commit, every checker on push
uv run tox               # run the full matrix
uv run tox -m check      # only the static checks
uv run tox -e py312      # or a single environment
```

## Links

- **Documentation**: https://mt940.readthedocs.io/
- **Source**: https://github.com/WoLpH/mt940
- **Bug reports**: https://github.com/WoLpH/mt940/issues
- **Package**: https://pypi.org/project/mt-940/
- **License**: [BSD-3-Clause](https://github.com/WoLpH/mt940/blob/develop/LICENSE)
