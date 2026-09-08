"""Exercise documentation checks against small, isolated source trees."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from docs._tools import inventory

if TYPE_CHECKING:
    from pathlib import Path


def _write(path: Path, lines: list[str]) -> None:
    """Write a Python fixture without implicit string concatenation."""
    _ = path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def test_inventory_includes_private_nested_and_attribute_definitions(
    tmp_path: Path,
) -> None:
    package: Path = tmp_path / 'sample'
    package.mkdir()
    _write(
        package / '__init__.py',
        [
            '"Sample package."',
            '#: A public constant.',
            'LIMIT: int = 2',
            'class Model:',
            '    "Sample model."',
            '    def __init__(self) -> None:',
            '        "Create a model."',
            '        self.value: int = 1',
            'def _factory():',
            '    "Build a callback."',
            '    def callback():',
            '        "Return a value."',
            '        return 1',
            '    return callback',
        ],
    )
    symbols: dict[str, inventory.Symbol] = inventory.collect(package)
    assert set(symbols) == {
        'sample',
        'sample.LIMIT',
        'sample.Model',
        'sample.Model.__init__',
        'sample.Model.value',
        'sample._factory',
        'sample._factory.callback',
    }
    assert symbols['sample._factory.callback'].anchor == 'sample._factory'
    assert symbols['sample.Model.value'].anchor == 'sample.Model'


def test_overloads_have_one_canonical_implementation(tmp_path: Path) -> None:
    package: Path = tmp_path / 'sample'
    package.mkdir()
    _write(
        package / '__init__.py',
        [
            '"Package."',
            'from typing import overload',
            '@overload',
            'def get(value: int) -> int: ...',
            'def get(value):',
            '    "Return value."',
            '    return value',
        ],
    )
    symbols: dict[str, inventory.Symbol] = inventory.collect(package)
    assert symbols['sample.get'].documented


def test_check_rejects_missing_stale_and_undocumented_entries(
    tmp_path: Path,
) -> None:
    package: Path = tmp_path / 'sample'
    package.mkdir()
    _write(
        package / '__init__.py',
        [
            '"Package."',
            'def missing():',
            '    return 1',
        ],
    )
    manifest: Path = tmp_path / 'inventory.json'
    _ = manifest.write_text(
        json.dumps({
            'sample': {
                'reference': 'sample.html',
                'guides': [],
                'tests': [],
                'symbols': ['sample', 'sample.removed'],
            }
        }),
        encoding='utf-8',
    )
    errors: list[str] = inventory.check_source(package, manifest)
    assert any('unlisted symbol: sample.missing' in error for error in errors)
    assert any('stale symbol: sample.removed' in error for error in errors)
    assert 'missing docstring: sample.missing' in errors


def test_rendered_check_requires_real_anchors_and_guide_files(
    tmp_path: Path,
) -> None:
    html: Path = tmp_path / 'html'
    html.mkdir()
    _ = (html / 'sample.html').write_text(
        '<section id="sample"><h1>Sample</h1></section>', encoding='utf-8'
    )
    symbols: dict[str, inventory.Symbol] = {
        'sample': inventory.Symbol(
            'sample', 'sample', 'module', documented=True
        ),
        'sample.work': inventory.Symbol(
            'sample.work', 'sample.work', 'function', documented=True
        ),
    }
    records: dict[str, inventory.Record] = {
        'sample': {
            'reference': 'sample.html',
            'guides': ['guide.html'],
            'tests': [],
            'symbols': list(symbols),
        }
    }
    errors: list[str] = inventory.check_rendered(symbols, records, html)
    assert any('sample.work' in error for error in errors)
    assert any('guide.html' in error for error in errors)


def test_inventory_finds_guarded_definitions_and_relative_exports(
    tmp_path: Path,
) -> None:
    package: Path = tmp_path / 'sample'
    package.mkdir()
    _write(
        package / '__init__.py',
        [
            '"Package."',
            'from .core import work as public_work',
            'if True:',
            '    def guarded():',
            '        "Guarded callable."',
            '        return 1',
        ],
    )
    _write(
        package / 'core.py',
        [
            '"Implementation."',
            'def work():',
            '    "Return a value."',
            '    return 1',
        ],
    )
    symbols: dict[str, inventory.Symbol] = inventory.collect(package)
    assert 'sample.guarded' in symbols
    assert symbols['sample.public_work'].anchor == 'sample.core.work'


def test_nested_class_attributes_belong_to_their_own_class(
    tmp_path: Path,
) -> None:
    package: Path = tmp_path / 'sample'
    package.mkdir()
    _write(
        package / '__init__.py',
        [
            '"Package."',
            'class Outer:',
            '    "Outer."',
            '    class Inner:',
            '        "Inner with value."',
            '        def __init__(self):',
            '            "Set value."',
            '            self.value = 1',
        ],
    )
    symbols: dict[str, inventory.Symbol] = inventory.collect(package)
    assert 'sample.Outer.Inner.value' in symbols
    assert 'sample.Outer.value' not in symbols


def test_module_constants_require_their_own_rendered_targets(
    tmp_path: Path,
) -> None:
    package: Path = tmp_path / 'sample'
    package.mkdir()
    _write(
        package / '__init__.py',
        [
            '"Package."',
            '#: Supported exports.',
            '__all__: list[str] = []',
        ],
    )
    symbols: dict[str, inventory.Symbol] = inventory.collect(package)
    assert symbols['sample.__all__'].anchor == 'sample.__all__'
    _ = (tmp_path / 'sample.html').write_text(
        '<section id="module-sample">Package</section>', encoding='utf-8'
    )
    records: dict[str, inventory.Record] = {
        'sample': {
            'reference': 'sample.html',
            'guides': [],
            'tests': [],
            'symbols': list(symbols),
        }
    }
    assert any(
        'sample.__all__' in error
        for error in inventory.check_rendered(symbols, records, tmp_path)
    )


def test_attribute_documentation_requires_a_complete_identifier(
    tmp_path: Path,
) -> None:
    package: Path = tmp_path / 'sample'
    package.mkdir()
    _write(
        package / '__init__.py',
        [
            '"Package."',
            'class Model:',
            '    "Avoid holding resources."',
            '    id: int = 1',
            '    def __init__(self):',
            '        "Avoid holding resources."',
            '        self.id = 2',
        ],
    )
    assert not inventory.collect(package)['sample.Model.id'].documented


def test_inventory_includes_unpacked_constants_and_chained_aliases(
    tmp_path: Path,
) -> None:
    package: Path = tmp_path / 'sample'
    package.mkdir()
    _write(
        package / '__init__.py',
        [
            '"Package."',
            'from .bridge import public_work',
            '#: Supported limits.',
            'MINIMUM, MAXIMUM = 1, 2',
        ],
    )
    _write(
        package / 'bridge.py',
        [
            '"Exports."',
            'from .core import work as public_work',
        ],
    )
    _write(
        package / 'core.py',
        [
            '"Implementation."',
            'def work():',
            '    "Return a value."',
            '    return 1',
        ],
    )
    symbols: dict[str, inventory.Symbol] = inventory.collect(package)
    assert symbols['sample.public_work'].anchor == 'sample.core.work'
    assert symbols['sample.MINIMUM'].documented
    assert symbols['sample.MAXIMUM'].documented


def test_unpacked_instance_attributes_exclude_ordinary_locals(
    tmp_path: Path,
) -> None:
    package: Path = tmp_path / 'sample'
    package.mkdir()
    _write(
        package / '__init__.py',
        [
            '"Package."',
            'class Model:',
            '    "Store left and right."',
            '    def __init__(self):',
            '        "Assign values."',
            '        self.left, self.right, local = 1, 2, 3',
        ],
    )
    symbols: dict[str, inventory.Symbol] = inventory.collect(package)
    assert symbols['sample.Model.left'].documented
    assert symbols['sample.Model.right'].documented
    assert 'sample.Model.local' not in symbols
