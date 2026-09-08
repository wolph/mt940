Installation
============

Install the ``mt-940`` distribution, then import ``mt940``. The runtime requires
Python 3.10 or newer and uses only the standard library.

In a project with an active virtual environment, install from PyPI:

.. code-block:: console

   uv pip install mt-940

For a new directory, create and activate an environment first. On a POSIX shell:

.. code-block:: console

   uv venv --python 3.12
   . .venv/bin/activate
   uv pip install mt-940

On Windows PowerShell, activation is ``.venv\Scripts\Activate.ps1``.
If you already manage packages with pip, ``python -m pip install mt-940``
installs the same distribution.

Verify the import in that environment:

.. doctest::

   >>> import mt940
   >>> isinstance(mt940.parse(':20:INSTALL-CHECK'), mt940.models.Transactions)
   True

A successful import and a parsed reference confirm that the package is usable.
Continue with :doc:`quickstart` for a complete statement.

Development checkout
--------------------

Contributors use Python 3.12 for the tools and documentation builder. This
requirement does not raise the library's Python 3.10 runtime minimum:

.. code-block:: console

   git clone --branch develop https://github.com/WoLpH/mt940.git
   cd mt940
   uv sync --python 3.12
   uv run lefthook install
   uv run tox -e py312

``uv sync`` installs the project and its development dependency group.
``develop`` receives changes. ``master`` tracks the stable release.
See :doc:`contributing` before preparing a change.
