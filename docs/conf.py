"""Sphinx configuration for the mt940 documentation.

The API reference pages are generated from the source on every build (locally,
on Read the Docs and in CI) by running ``sphinx-apidoc`` from the
``builder-inited`` hook below, so the generated ``mt940*.rst`` files do not need
to be committed.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sphinx.application import Sphinx

DOCS_ROOT = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.dirname(DOCS_ROOT)
PACKAGE_ROOT = os.path.join(PROJECT_ROOT, 'mt940')

# Make the package importable and single-source its metadata.
sys.path.insert(0, PROJECT_ROOT)
_about: dict[str, str] = {}
with open(os.path.join(PACKAGE_ROOT, '__about__.py')) as _fh:
    exec(_fh.read(), _about)

# -- Project information ------------------------------------------------------
project = _about['__title__']
author = _about['__author__']
copyright = _about['__copyright__']  # noqa: A001
release = _about['__version__']
version = '.'.join(release.split('.')[:2])

# -- General configuration ----------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx.ext.doctest',
]
exclude_patterns = ['_build', 'html', 'doctrees']

# -- Autodoc / Napoleon -------------------------------------------------------
autodoc_typehints = 'description'
autodoc_member_order = 'bysource'
autodoc_default_options = {
    'members': True,
    'show-inheritance': True,
}
napoleon_google_docstring = True
napoleon_numpy_docstring = False

intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
}

# -- HTML output --------------------------------------------------------------
html_theme = 'furo'
html_title = f'{project} {release}'


# -- Generate the API reference on every build --------------------------------
def _run_apidoc(app: Sphinx) -> None:
    """Regenerate the ``mt940*.rst`` API pages from the package source."""
    from sphinx.ext import apidoc

    apidoc.main(
        [
            '--force',
            '--separate',
            '--module-first',
            '--output-dir',
            DOCS_ROOT,
            PACKAGE_ROOT,
        ]
    )


def setup(app: Sphinx) -> None:
    """Connect the apidoc generation step to the build."""
    app.connect('builder-inited', _run_apidoc)
