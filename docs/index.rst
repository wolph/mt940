MT940 for Python
================

Read bank statement text into transactions, decimal amounts, dates and balances.
``mt940`` has no runtime dependencies and includes type information for Python
3.10 through 3.15.

.. container:: guide-grid

   .. container:: guide-card

      .. rubric:: Parse a first statement

      :doc:`quickstart` uses a complete fictional statement, then reads its
      transaction and closing balance. No bank file or checkout is needed.

   .. container:: guide-card

      .. rubric:: Keep statement metadata

      :doc:`statements` explains merged files, separate ``:20:`` blocks and
      transaction grouping within a statement.

   .. container:: guide-card

      .. rubric:: Adapt a bank export

      :doc:`customising` builds isolated tag overrides and ordered processors.
      :doc:`compatibility` explains all ten opt-in switches.

   .. container:: guide-card

      .. rubric:: Ship an integration

      :doc:`json` follows a synthetic file through validation, reconciliation
      and a JSON report. :doc:`troubleshooting` diagnoses common surprises.

The parser preserves the values it recognises. It does not verify a bank's
signature, calculate balances or guarantee that an export is complete. Your
application decides which fields and reconciliation checks it requires.

.. toctree::
   :caption: Start here
   :maxdepth: 1

   installation
   quickstart
   usage

.. toctree::
   :caption: Guides
   :maxdepth: 1

   inputs
   data-model
   statements
   json
   customising
   bank-formats
   compatibility
   troubleshooting

.. toctree::
   :caption: Reference
   :maxdepth: 1

   modules
   internals

.. toctree::
   :caption: Contributing
   :maxdepth: 1

   contributing
   testing
   documentation
   releases

Find a symbol through :ref:`genindex`, browse :ref:`modindex`, or use
:ref:`search`. Source and issue reports live on
`GitHub <https://github.com/WoLpH/mt940>`_.
