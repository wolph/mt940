Build and maintain the documentation
====================================

Documentation has two sources: authored guides and package docstrings. The
build generates the API reference, then checks that the reviewed symbol
inventory is represented in source and rendered HTML.

The source archive includes the guides, examples, tests and tool configuration
needed to rebuild the documentation. The wheel contains the runtime package.
Use Python 3.12 for the documentation tools:

.. code-block:: console

   uv sync --python 3.12
   uv run tox -e docs

The docs environment executes the runnable-example tests, checks source
inventory coverage, runs Sphinx doctests and builds HTML with warnings and
missing references treated as errors. It then checks rendered symbol anchors,
required guide pages and local links. HTML is written under ``docs/html``.

Inspect individual checks
-------------------------

These commands expose the source, executable-content and rendered checks
separately:

.. code-block:: console

   uv run python -m docs._tools.inventory
   uv run sphinx-build -W -n --keep-going -b doctest docs docs/_build/doctest
   uv run sphinx-build -W -n --keep-going -b html docs docs/html
   uv run python -m docs._tools.inventory --html docs/html
   uv run python -m docs._tools.links docs/html

``docs._tools.symbols`` collects source definitions and their ownership through
the Python syntax tree. ``docs._tools.reference`` generates the API pages from
that collection. ``docs._tools.inventory`` compares the collected symbols with
``docs/inventory.json`` and checks the built reference anchors and guide
coverage. ``docs._tools.links`` resolves local rendered links and fragments.

The checked-in inventory is a reviewed map, not an excuse to accept every new
symbol automatically. When adding, removing or moving a definition, inspect
its reference anchor and decide which authored guides explain its purpose.
Update the inventory alongside that review. Nested helper references can point
to their enclosing function, and instance attributes can point to their owning
class where Sphinx documents them. The tool tests protect those rules.

Do not hand-edit ``docs/mt940*.rst`` or ``docs/modules.rst``. The reference
generator rewrites them during builds. Change the source docstring or generator
when the rendered API needs correction. Public package aliases resolve to
their canonical module definitions.

Write examples that run
-----------------------

Use a self-contained ``doctest`` directive for short examples with output.
Use ``testcode`` and ``testoutput`` when a complete script reads better.
For checkout examples, include the tested file from ``examples`` with
``literalinclude`` and include its recorded stdout separately.

A plain Python code block is only appropriate for an explicitly described
fragment that cannot run by itself. Do not imply such a fragment is a recorded
execution. Keep raw bank fixtures out of guide pages. The synthetic fixtures
under ``examples/fixtures`` are intended for display.

Preserve existing page URLs, including ``installation``, ``usage``, ``index``
and ``contributing``. The landing page groups Start here, Guides, Reference and
Contributing. Its ``guide-grid`` and ``guide-card`` containers provide cards in
HTML while retaining ordinary content in EPUB and PDF. The ``pipeline``
container uses ordered text so parser stages remain accessible without CSS.

Review the rendered result
--------------------------

A warning-free build verifies structure and references, not visual quality.
Serve the built site locally:

.. code-block:: console

   uv run python -m http.server 8000 --bind 127.0.0.1 --directory docs/html

Inspect the landing page, the changed guides and affected reference sections
in the browser. Check full pages and close views of tables, code blocks,
headings and navigation. Repeat at desktop, 768px tablet and 375px mobile widths,
including light and dark themes. Verify wrapping, contrast, horizontal
scrolling and focus states, and check the browser console for errors.

Open exported EPUB and PDF too. Tables, long identifiers and code samples can
wrap differently from HTML. Inspect representative pages containing the
landing cards, tag tables, pipeline, source examples and API signatures.
CI preview artefacts are retained for seven days for this review.

Other formats and external links
--------------------------------

Tectonic is required on ``PATH`` for PDF compilation. On macOS:

.. code-block:: console

   brew install tectonic
   uv run tox -e docs-formats

The formats environment builds EPUB, generates LaTeX through Sphinx and
compiles the PDF with Tectonic. Read the environment's output paths for the
resulting artefacts. Read the Docs uses Python 3.12 with warning failures and
builds PDF and EPUB too.

Source buttons on Read the Docs point to the branch or tag being built.
Pull request previews use the checked-out commit. Local builds use
``develop`` unless you set ``READTHEDOCS_GIT_IDENTIFIER`` to another Git ref.

Remote sites can fail independently of a documentation change. Run the
separate network-dependent check when reviewing external links:

.. code-block:: console

   uv run tox -e docs-linkcheck

Investigate each failure as a stale URL, redirect, access restriction or
transient network problem. Do not weaken local anchor or inventory checks to
silence an unrelated remote error.
