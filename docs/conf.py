"""Build the public guides and canonical Python references for MT940.

The same configuration is used by tox, local builds and Read the Docs. Module
pages are generated on every build. Their source templates live in
``docs._tools.reference`` and their content comes from package docstrings.
"""

from __future__ import annotations

import doctest
import pathlib
import shutil
import sys
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from docutils import nodes
    from sphinx.addnodes import pending_xref
    from sphinx.application import Sphinx
    from sphinx.environment import BuildEnvironment

DOCS_ROOT: pathlib.Path = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT: pathlib.Path = DOCS_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mt940 import __about__ as _about  # noqa: E402

from docs._tools import reference  # noqa: E402

project: str = _about.__title__
author: str = _about.__author__
copyright: str = _about.__copyright__.removeprefix('Copyright ')  # noqa: A001
release: str = _about.__version__
version: str = '.'.join(release.split('.')[:2])

extensions: list[str] = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx.ext.doctest',
]
# Only owned Python modules have useful source pages. Following re-exports
# can leave source-index links to compiled modules such as _abc and builtins.
viewcode_follow_imported_members: bool = False
smartquotes: bool = False
doctest_default_flags: int = (
    doctest.NORMALIZE_WHITESPACE
    | doctest.IGNORE_EXCEPTION_DETAIL
    | doctest.ELLIPSIS
)
exclude_patterns: list[str] = [
    '_build',
    'html',
    'doctrees',
    '_tools',
    'superpowers',
]

autodoc_typehints: str = 'description'
autodoc_member_order: str = 'bysource'
autodoc_default_options: dict[str, str | bool] = {
    'members': True,
    'show-inheritance': True,
    'special-members': (
        '__init__,__new__,__call__,__eq__,__hash__,__getitem__,__len__,'
        '__repr__,__str__,__getstate__,__setstate__'
    ),
}
napoleon_google_docstring: bool = True
napoleon_numpy_docstring: bool = False
napoleon_include_private_with_doc: bool = True
napoleon_include_special_with_doc: bool = True
napoleon_use_ivar: bool = True
intersphinx_mapping: dict[str, tuple[str, None]] = {
    'python': ('https://docs.python.org/3/', None),
}
nitpicky: bool = True
# A TypeVar is a type-checking placeholder, not a Python class target.
nitpick_ignore: list[tuple[str, str]] = [('py:class', 'mt940.utils.T')]

html_theme: str = 'furo'
html_title: str = f'{project} {release}'
html_static_path: list[str] = ['_static']
html_css_files: list[str] = ['custom.css']
html_theme_options: dict[str, object] = {
    'source_repository': 'https://github.com/WoLpH/mt940/',
    'source_branch': 'develop',
    'source_directory': 'docs/',
    'light_css_variables': {
        'color-brand-primary': '#195f73',
        'color-brand-content': '#195f73',
        'color-highlight-on-target': '#e5f1f4',
    },
    'dark_css_variables': {
        'color-brand-primary': '#77cddd',
        'color-brand-content': '#77cddd',
        'color-highlight-on-target': '#102128',
    },
}
html_show_sphinx: bool = False
html_copy_source: bool = True

epub_title: str = 'MT940: parsing bank statements with Python'
epub_author: str = author
epub_language: str = 'en'
epub_tocdepth: int = 2
epub_show_urls: str = 'no'
epub_exclude_files: list[str] = ['search.html', '.buildinfo.bak']
latex_documents: list[tuple[str, str, str, str, str]] = [
    (
        'index',
        'mt940.tex',
        'MT940: parsing bank statements with Python',
        author,
        'manual',
    ),
]
# Links remain clickable. Printing every type-reference URL creates hundreds
# of repeated footnotes and can overflow a PDF page.
latex_show_urls: str = 'no'
latex_engine: str = 'xelatex'
latex_elements: dict[str, str] = {
    'papersize': 'a4paper',
    'pointsize': '10pt',
    # The first HTML navigation group is narrower than the PDF contents.
    'tableofcontents': (
        r'\renewcommand{\contentsname}{Contents}\sphinxtableofcontents'
    ),
}


def _generate_reference(app: Sphinx) -> None:
    """Regenerate the API pages from maintained templates and docstrings."""
    reference.generate(PROJECT_ROOT / 'mt940', DOCS_ROOT)
    # Viewcode checks module timestamps only. New reference members and changed
    # navigation also need fresh source HTML when the module is unchanged.
    source_pages: pathlib.Path = pathlib.Path(app.outdir) / '_modules'
    if app.builder.format == 'html' and source_pages.is_dir():
        shutil.rmtree(source_pages)


def _resolve_alias(
    app: Sphinx,
    env: BuildEnvironment,
    node: pending_xref,
    content: nodes.Element,
) -> nodes.reference | None:
    """Resolve documented re-exports to their single defining-module target.

    Returns:
        The canonical reference, or None for Sphinx's remaining resolvers.
    """
    aliases: dict[str, str] = {
        'parse': 'mt940.parser.parse',
        'parse_statements': 'mt940.parser.parse_statements',
        'JSONEncoder': 'mt940.json.JSONEncoder',
        'mt940.parse': 'mt940.parser.parse',
        'mt940.parse_statements': 'mt940.parser.parse_statements',
        'mt940.JSONEncoder': 'mt940.json.JSONEncoder',
        'mt940.Options': 'mt940.options.Options',
        'Source': 'mt940._types.Source',
        'Processors': 'mt940._types.Processors',
        'PreProcessor': 'mt940._types.PreProcessor',
        'PostProcessor': 'mt940._types.PostProcessor',
        'TagDict': 'mt940._types.TagDict',
    }
    target: str = node.get('reftarget', '')
    if target == 're.error':
        # The old name remains the exception API on supported Python releases.
        # Python's inventory indexes the same exception as PatternError.
        node['reftarget'] = 're.PatternError'
        return None
    if target not in aliases:
        return None
    return env.get_domain('py').resolve_xref(
        env,
        cast('str', node['refdoc']),
        app.builder,
        'obj',
        aliases[target],
        node,
        content,
    )


def _reference_source_links(
    _app: Sphinx,
    pagename: str,
    _templatename: str,
    context: dict[str, object],
    _doctree: nodes.document | None,
) -> None:
    """Point generated-page toolbar links at their maintained source files."""
    source: str
    if pagename == 'modules':
        source = 'docs/_tools/reference.py'
    elif pagename == 'mt940':
        source = 'mt940/__init__.py'
    elif pagename.startswith('mt940.'):
        source = pagename.replace('.', '/') + '.py'
    else:
        return
    repository: str = 'https://github.com/WoLpH/mt940'
    context['theme_source_edit_link'] = f'{repository}/edit/develop/{source}'
    context['theme_source_view_link'] = f'{repository}/blob/develop/{source}'


def setup(app: Sphinx) -> None:
    """Generate references before Sphinx discovers source documents."""
    _ = app.connect('builder-inited', _generate_reference)
    _ = app.connect('missing-reference', _resolve_alias, priority=400)
    _ = app.connect('html-page-context', _reference_source_links)
