# MT940

[![CI](https://github.com/WoLpH/mt940/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/WoLpH/mt940/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/mt-940)](https://pypi.org/project/mt-940/)
[![Python](https://img.shields.io/pypi/pyversions/mt-940)](https://pypi.org/project/mt-940/)
[![Downloads](https://img.shields.io/pypi/dm/mt-940)](https://pypi.org/project/mt-940/)
[![Documentation](https://readthedocs.org/projects/mt940/badge/?version=latest)](https://mt940.readthedocs.io/)
[![Coverage](https://coveralls.io/repos/github/WoLpH/mt940/badge.svg?branch=develop)](https://coveralls.io/github/WoLpH/mt940?branch=develop)
[![License](https://img.shields.io/pypi/l/mt-940)](https://github.com/WoLpH/mt940/blob/develop/LICENSE)

`mt940` is a library to parse MT940 files and return smart Python collections
for statistics and manipulation. It has no runtime dependencies, is fully type
annotated (`py.typed`), and ships smart models that make working with bank
statements straightforward.

## Quick Start

```bash
pip install mt-940
```

```python
import mt940
import pprint

transactions = mt940.parse('mt940_tests/jejik/abnamro.sta')

print('Transactions:')
print(transactions)
pprint.pprint(transactions.data)

for transaction in transactions:
    print('Transaction: ', transaction)
    pprint.pprint(transaction.data)
```

## Usage

### Set opening / closing balance information on each transaction

```python
import mt940
import pprint

mt940.tags.BalanceBase.scope = mt940.models.Transaction

# The currency has to be set manually when setting the BalanceBase scope to
# Transaction.
transactions = mt940.models.Transactions(processors=dict(
    pre_statement=[
        mt940.processors.add_currency_pre_processor('EUR'),
    ],
))

with open('mt940_tests/jejik/abnamro.sta') as f:
    data = f.read()

transactions.parse(data)

for transaction in transactions:
    print('Transaction: ', transaction)
    pprint.pprint(transaction.data)
```

### Simple JSON encoding

```python
import json
import mt940

transactions = mt940.parse('mt940_tests/jejik/abnamro.sta')

print(json.dumps(transactions, indent=4, cls=mt940.JSONEncoder))
```

### Parsing statements from the Dutch bank ASN

Tag 61 in ASN statements does not follow the SWIFT specification, so a custom
tag is used:

```python
import pprint
import mt940


def ASNB_mt940_data():
    with open('mt940_tests/ASNB/0708271685_09022020_164516.940.txt') as fh:
        return fh.read()


tag_parser = mt940.tags.StatementASNB()
trs = mt940.models.Transactions(tags={tag_parser.id: tag_parser})
trs.parse(ASNB_mt940_data())

print(pprint.pformat(trs.data, sort_dicts=False))
```

### Transaction grouping (opt-in)

By default a new transaction is started only on the `:61:` statement tag.
Some banks delimit transactions differently — for example by repeating the
`:20:` transaction reference per block. Because changing the default grouping
would break existing users, this behaviour is **opt-in**: pass
`transaction_boundary` (an iterable of tag *slugs*) to start a new transaction
on those tags too. Omitting it preserves the historical behaviour.

```python
import mt940

# Each `:20:` (transaction_reference_number) starts its own transaction:
transactions = mt940.parse(
    data, transaction_boundary={'transaction_reference_number'}
)
```

The same option is accepted by `mt940.models.Transactions(transaction_boundary=...)`.

### Banks with longer reference fields (opt-in)

Some banks (e.g. GLS / Atruvia) put a customer reference longer than the SWIFT
16-character cap on the `:61:` line, followed by the `//` bank reference.
Relaxing the default would change how other banks (e.g. Rabobank) split
same-line data, so this is handled by an **opt-in** `StatementGLS` tag:

```python
import mt940

gls = mt940.tags.StatementGLS()
transactions = mt940.parse(data, tags={gls.id: gls})
```

(Longer *supplementary details* — issue #117, e.g. Wise — are handled by the
default parser and need no opt-in.)

## Contributing

Help is greatly appreciated. Please clone the **develop** branch and run `tox`
before opening a pull request; CI checks linting (ruff), type-checking
(pyright, mypy, pyrefly), the test suite (100% coverage required), and the
documentation build.

```bash
git clone --branch develop https://github.com/WoLpH/mt940.git
cd mt940
uv sync
uv run tox          # run the full matrix
uv run tox -e py312 # or a single environment
```

## Links

- **Documentation**: https://mt940.readthedocs.io/
- **Source**: https://github.com/WoLpH/mt940
- **Bug reports**: https://github.com/WoLpH/mt940/issues
- **Package**: https://pypi.org/project/mt-940/
- **License**: [BSD-3-Clause](https://github.com/WoLpH/mt940/blob/develop/LICENSE)
