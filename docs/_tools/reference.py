"""Generate canonical references with one target per definition."""

from pathlib import Path


def generate(package: Path, destination: Path) -> None:
    """Write deterministic API pages, retaining the project's existing URLs."""
    modules: list[str] = []
    for path in sorted(package.glob('*.py')):
        module: str = (
            package.name
            if path.stem == '__init__'
            else f'{package.name}.{path.stem}'
        )
        modules.append(module)
        title: str = 'Package API' if path.stem == '__init__' else module
        content: str = (
            f'{title}\n{"=" * len(title)}\n\n.. automodule:: {module}\n'
        )
        if path.stem == '__init__':
            content += '   :no-members:\n\n'
            content += (
                'Public entry points\n-------------------\n\n'
                '* :func:`mt940.parser.parse`\n'
                '* :func:`mt940.parser.parse_statements`\n'
                '* :class:`mt940.options.Options`\n'
                '* :class:`mt940.json.JSONEncoder`\n\n'
                'Import these directly from ``mt940``. The module exports\n'
                '``models``, ``parser``, ``processors``, ``tags``,\n'
                '``utils``, '
                '``json`` and ``__version__``.\n'
            )
        else:
            content += (
                '   :members:\n   :private-members:\n   :undoc-members:\n'
            )
        (destination / f'{module}.rst').write_text(content, encoding='utf-8')
    index: str = (
        'API reference\n=============\n\n'
        'The reference follows the source modules. Read :doc:`data-model`\n'
        'for returned fields or :doc:`customising` for extension examples.\n\n'
        '.. toctree::\n   :maxdepth: 1\n\n'
    )
    index += ''.join(f'   {module}\n' for module in modules)
    (destination / 'modules.rst').write_text(index, encoding='utf-8')
