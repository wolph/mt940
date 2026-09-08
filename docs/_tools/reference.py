"""Generate canonical references with one target per definition."""

from pathlib import Path

from .symbols import Symbol, collect


def generate(package: Path, destination: Path) -> None:
    """Write deterministic API pages, retaining the project's existing URLs."""
    modules: list[str] = []
    symbols: dict[str, Symbol] = collect(package)
    for path in sorted(package.glob('*.py')):
        module: str = (
            package.name
            if path.stem == '__init__'
            else f'{package.name}.{path.stem}'
        )
        modules.append(module)
        title: str = 'Package API' if path.stem == '__init__' else module
        content: str = (
            f'{title}\n{"=" * len(title)}\n\n'
            '.. testsetup::\n\n'
            '   import importlib as _importlib\n'
            '   globals().update(vars('
            f'_importlib.import_module("{module}")))\n'
            f'\n.. automodule:: {module}\n'
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
            content += '   :members:\n   :private-members:\n'
        special: list[str] = [
            name
            for name, symbol in symbols.items()
            if symbol.kind == 'attribute'
            and name.rsplit('.', 1)[0] == module
            and name.rsplit('.', 1)[1].startswith('__')
        ]
        if special and path.stem == '__init__':
            content += '\n' + '\n'.join(
                f'.. autodata:: {name}\n' for name in special
            )
        output: Path = destination / f'{module}.rst'
        _ = output.write_text(content, encoding='utf-8')
    index: str = (
        'API reference\n=============\n\n'
        'The reference follows the source modules. See :doc:`data-model`\n'
        'for returned fields or :doc:`customising` for extension examples.\n\n'
        '.. toctree::\n   :maxdepth: 1\n\n'
    )
    index += ''.join(f'   {module}\n' for module in modules)
    _ = (destination / 'modules.rst').write_text(index, encoding='utf-8')
