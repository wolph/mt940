Run tests and maintain fixtures
===============================

Use a focused test while reproducing a problem, then run the supported matrix
before treating the change as ready. From a Python 3.12 development checkout:

.. code-block:: console

   uv sync --python 3.12
   uv run lefthook install
   uv run pytest --no-cov mt940_tests/test_parse.py
   uv run tox -e py312
   uv run tox

The first pytest command intentionally disables coverage for a narrow test
selection. The matrix measures package and test code with branch coverage,
combines results and requires 100%. Python 3.10 through 3.15 are separate tox
environments. Check the output for skipped interpreters because the local tox
configuration permits skips.

The Python 3.15 CI job uses the newest available interpreter, including release
candidates until the final release is available.

Fixture organisation
--------------------

Bank and source-provider directories contain ``.sta`` input files and ``.yml``
expected model output. ``test_sta_parsing.py`` discovers the statement files
recursively. Each fixture is parsed under default ``Options`` and
``Options.all()``. A sibling ``.all.yml`` overrides the default expectation
when the enabled options change output. Otherwise both modes reuse the
ordinary ``.yml`` file.

Golden comparisons check statement metadata, transaction data and model
attributes recursively. They report the path of the first difference, such as
an amount inside a transaction. JSON serialisation is exercised for every
fixture too. YAML expectations contain Python model tags and are trusted
repository test data, not a format to load from untrusted reports.

For a new case, start with fictional data that preserves the failing format.
After deliberately changing expected behaviour, regenerate only the relevant
fixture selection:

.. code-block:: console

   WRITE_YAML_FILES=1 uv run pytest --no-cov \
       mt940_tests/test_sta_parsing.py -k fixture_name
   git diff -- mt940_tests

``fixture_name`` is a placeholder for the new fixture's test selection. The
write flag changes expectation files, so inspect every changed field. Rerun
the same test without the flag to confirm the checked-in expectation passes.
An output change is not justified merely because regeneration produced it.

Expected failures
-----------------

The suite uses strict expected failures for known limitations. A test marked
``xfail`` is a recorded failing requirement, not a successful implementation.
An unexpected pass fails the suite so that the marker and any compatibility
implications receive review.

The paged-statement regression for the first intermediate balance is one such
case. A single ``:20:`` block can contain multiple pages, but repeated balance
keys retain the last value. ``parse_statements`` does not split ``:28C:`` pages.
Keep that limitation visible until the behaviour is intentionally addressed.

Runnable examples and transcripts
---------------------------------

The ``examples`` package has synthetic fixtures, executable modules and their
recorded stdout under ``examples/output``. Run an example from the checkout:

.. code-block:: console

   uv run python -m examples.basic
   uv run python -m examples.walkthrough
   uv run pytest --no-cov mt940_tests/test_examples.py

The tests execute all example modules and compare stdout with the recorded
files. Semantic checks also verify amounts, balance reconciliation and JSON
decimal strings. The primary Python fence in ``README.md`` is extracted and
executed, so its self-contained input and output cannot drift unnoticed.

When intentionally changing an example, run its command and redirect its
actual stdout to the corresponding output file, then review the full diff:

.. code-block:: console

   uv run python -m examples.basic > examples/output/basic.txt
   uv run pytest --no-cov mt940_tests/test_examples.py

Never patch the transcript by hand. Include the tested source and output with
``literalinclude`` in Sphinx. Authored Python snippets use ``doctest`` or
``testcode`` directives so the documentation build executes them.

Static, security and build gates
--------------------------------

.. list-table:: Checks and purpose
   :header-rows: 1
   :widths: 30 70

   * - Environment
     - Purpose
   * - ``lint``
     - Ruff rules and formatting check.
   * - ``mypy``, ``basedpyright``, ``pyright``, ``pyrefly``, ``ty``
     - Five independent type checkers over package, tests, examples and docs
       tooling. Docs configuration is checked with its Python 3.12 needs.
   * - ``taplo``
     - TOML formatting and validation.
   * - ``codespell``
     - Source and documentation spelling.
   * - ``repo-review``
     - Repository metadata and configuration conventions.
   * - ``zizmor``
     - GitHub Actions security analysis.
   * - ``audit``
     - Known vulnerabilities in installed dependencies.
   * - ``docs``
     - Executable examples, doctests, strict HTML, symbol inventory and local
       rendered-link checks.
   * - ``docs-formats``
     - EPUB, LaTeX generation and PDF compilation with Tectonic.
   * - ``docs-linkcheck``
     - Opt-in remote-link validation. Requires network access.
   * - ``coverage``
     - Combined branch coverage from all supported runtime environments.

``uv run tox -m check`` selects the static and audit environments. It does not
replace tests or the documentation checks. Release workflow builds additionally
validate distributions with ``twine check --strict``. CI uploads documentation
previews for inspection. :doc:`documentation` explains rendered review and
:doc:`releases` covers release verification.
