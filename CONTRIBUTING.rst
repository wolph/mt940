Contributing
============

Changes go to ``develop``. ``master`` tracks stable releases. A useful report
or patch includes a small reproducible input, the observed output and the
expected result.

Report a parsing problem
------------------------

Open an issue at https://github.com/WoLpH/mt940/issues with Python and package
versions, the operating system, source encoding, selected ``Options`` and any
custom tags or processors. Explain which field is wrong and why the source
requires a different result.

Reduce the input to synthetic data before sharing it. Preserve significant
line breaks, tag order, field lengths and separators, but remove account
numbers, customer names and bank references. Attach the complete traceback
when parsing raises. For incorrect output, show the smallest relevant field
comparison. A bank name alone does not identify an export format.

Set up a checkout
-----------------

Install Python 3.12 and uv, then clone the development branch:

.. code-block:: console

   git clone --branch develop https://github.com/WoLpH/mt940.git
   cd mt940
   uv sync --python 3.12
   uv run lefthook install
   git switch -c feature/describe-the-change

For a contribution from a fork, use your fork's clone URL. Keep ``develop`` as
the pull request target. The runtime minimum is Python 3.10. Python 3.12 is
used for contributor tools and documentation because the documentation stack
has a newer interpreter requirement.

Reproduce before changing behaviour
-----------------------------------

Write a focused test that fails for the reported behaviour. For bank format
changes, add a small ``.sta`` fixture and review its expected output. The fixture
suite runs default options and ``Options.all()`` separately, so a fix cannot
silently change compatibility output without a visible expectation change.

Keep tag and processor customisation local to the test. Built-in tag instances
and default callback lists are shared. Use a tag subclass and a replacement
processor list instead of modifying those shared objects. Do not use a global
balance-scope change to make one fixture pass.

Run focused checks while working:

.. code-block:: console

   uv run pytest --no-cov mt940_tests/test_parse.py
   uv run tox -e py312
   uv run tox -m check
   uv run tox -e docs

``--no-cov`` is useful for a deliberately narrow test run. The full suite still
needs its coverage gate. Before submitting, run the complete matrix:

.. code-block:: console

   uv run tox

Check that Python 3.10, 3.11, 3.12, 3.13 and 3.14 actually ran. Tox can skip a
missing interpreter. A locally successful command with skipped interpreters
does not establish the whole supported matrix.

Tests, tools and documentation
------------------------------

The suite includes bank fixtures, issue regressions, model and processor tests,
doctests, runnable examples and a test of the README's primary Python snippet.
Combined branch coverage is required to reach 100%. Strict expected failures
record known limitations and become failures if their behaviour changes.

Five type checkers run: mypy, basedpyright, pyright, pyrefly and ty. Ruff checks
every enabled rule and verifies formatting. The commit hook handles Python
formatting. Additional gates check spelling, TOML, repository configuration,
GitHub Actions security and installed dependencies.

For documentation changes, run ``uv run tox -e docs``. It tests examples,
checks the symbol inventory, executes doctests, builds strict HTML and checks
rendered symbols and local links. ``uv run tox -e docs-linkcheck`` checks remote
links and requires network access. ``uv run tox -e docs-formats`` builds EPUB,
LaTeX and PDF with Tectonic available on ``PATH``. On macOS, install Tectonic
with ``brew install tectonic``.

The Testing and Documentation guides in the built documentation describe
fixture layout, coverage, output recording and all documentation checks.
The published documentation is at https://mt940.readthedocs.io/.

Prepare the pull request
------------------------

Keep the change scoped to the reproduced problem. Describe the trigger and the
resulting behaviour, include the relevant tests and update the user guide or
API docstring when an interface changes. Add explicit type annotations to new
variables and signatures. Use decimal strings or ``Decimal`` for money.

Review ``git diff`` before staging named files. Generated API pages come from
source docstrings and documentation tooling. Do not hand-edit them. When adding
or removing package symbols, review ``docs/inventory.json`` and map the symbols
to the appropriate guides as part of the same change.

Write documentation with British spelling and ASCII punctuation. README images
use absolute URLs. Use synthetic examples, include their tested source files
in Sphinx and regenerate displayed output by executing the examples. Do not
change a recorded output line by hand to match an explanation.

Before submission, confirm the full CI result and inspect all required matrix
jobs. Report any check you could not run, including missing interpreters or
external tools. Release work has additional verification described in the
release guide. A contributor patch does not publish a release.
