"""Sphinx configuration for the mt940 documentation.

The API reference pages are generated from the source on every build
(locally, on Read the Docs and in CI) by running ``sphinx-apidoc`` from the
``builder-inited`` hook below, so the generated ``mt940*.rst`` files do not
need to be committed.
"""

from __future__ import annotations

import pathlib
import sys
from typing import TYPE_CHECKING

from sphinx.ext import apidoc

if TYPE_CHECKING:
    from sphinx.application import Sphinx

DOCS_ROOT = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = DOCS_ROOT.parent
PACKAGE_ROOT = PROJECT_ROOT / 'mt940'

# Make the package importable and single-source its metadata.
sys.path.insert(0, str(PROJECT_ROOT))

from mt940 import __about__ as _about  # noqa: E402 (needs the sys.path entry)

# -- Project information ------------------------------------------------------
project = _about.__title__
author = _about.__author__
copyright = _about.__copyright__  # noqa: A001 (Sphinx setting name)
release = _about.__version__
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

# -- Cross-reference strictness -----------------------------------------------
# Treat unresolved references as errors so the ``-W`` build used in CI catches
# broken links. The entries below are references autodoc emits for objects that
# cannot have a documentation target: PEP 613 type aliases and TypeVars are not
# classes, and the processor protocols live in the private ``mt940._types``
# leaf
# module that is intentionally excluded from the public API reference.
nitpicky = True
nitpick_ignore = [
    ('py:class', 'Source'),
    ('py:class', 'Processors'),
    ('py:class', 'mt940.utils.T'),
    ('py:class', 'mt940._types.PreProcessor'),
    ('py:class', 'mt940._types.PostProcessor'),
    # The same protocols as they appear in postponed (string) annotations.
    ('py:class', 'PreProcessor'),
    ('py:class', 'PostProcessor'),
]

# -- HTML output --------------------------------------------------------------
html_theme = 'furo'
html_title = f'{project} {release}'


# -- Generate the API reference on every build --------------------------------
def _run_apidoc(_app: Sphinx) -> None:
    """Regenerate the ``mt940*.rst`` API pages from the package source."""
    _ = apidoc.main([
        '--force',
        '--separate',
        '--module-first',
        '--output-dir',
        str(DOCS_ROOT),
        str(PACKAGE_ROOT),
    ])


def setup(app: Sphinx) -> None:
    """Connect the apidoc generation step to the build."""
    _ = app.connect('builder-inited', _run_apidoc)
