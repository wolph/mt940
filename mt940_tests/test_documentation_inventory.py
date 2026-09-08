"""Exercise documentation checks against small, isolated source trees."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from docs._tools import inventory


def test_inventory_includes_private_nested_and_attribute_definitions(
    tmp_path: Path,
) -> None:
    package: Path = tmp_path / 'sample'
    package.mkdir()
    source: Path = package / '__init__.py'
    source.write_text(
        '"""Sample package."""\n'
        '#: A public constant.\nLIMIT: int = 2\n'
        'class Model:\n'
        '    """Sample model."""\n'
        '    def __init__(self) -> None:\n'
        '        """Create a model."""\n'
        '        self.value: int = 1\n'
        'def _factory():\n'
        '    """Build a callback."""\n'
        '    def callback():\n'
        '        """Return a value."""\n'
        '        return 1\n'
        '    return callback\n',
        encoding='utf-8',
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
    (package / '__init__.py').write_text(
        '"""Package."""\n'
        'from typing import overload\n'
        '@overload\ndef get(value: int) -> int: ...\n'
        'def get(value):\n    """Return value."""\n    return value\n',
        encoding='utf-8',
    )
    symbols: dict[str, inventory.Symbol] = inventory.collect(package)
    assert symbols['sample.get'].documented


def test_check_rejects_missing_stale_and_undocumented_entries(
    tmp_path: Path,
) -> None:
    package: Path = tmp_path / 'sample'
    package.mkdir()
    (package / '__init__.py').write_text(
        '"""Package."""\ndef missing():\n    return 1\n',
        encoding='utf-8',
    )
    manifest: Path = tmp_path / 'inventory.json'
    manifest.write_text(
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
    assert any(
        'missing docstring: sample.missing' in error for error in errors
    )


def test_rendered_check_requires_real_anchors_and_guide_files(
    tmp_path: Path,
) -> None:
    html: Path = tmp_path / 'html'
    html.mkdir()
    (html / 'sample.html').write_text(
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
    (package / '__init__.py').write_text(
        '"""Package."""\nfrom .core import work as public_work\n'
        'if True:\n'
        '    def guarded():\n        """Guarded callable."""\n'
        '        return 1\n',
        encoding='utf-8',
    )
    (package / 'core.py').write_text(
        '"""Implementation."""\n'
        'def work():\n    """Return a value."""\n    return 1\n',
        encoding='utf-8',
    )
    symbols: dict[str, inventory.Symbol] = inventory.collect(package)
    assert 'sample.guarded' in symbols
    assert symbols['sample.public_work'].anchor == 'sample.core.work'


def test_nested_class_attributes_belong_to_their_own_class(
    tmp_path: Path,
) -> None:
    package: Path = tmp_path / 'sample'
    package.mkdir()
    (package / '__init__.py').write_text(
        '"""Package."""\n'
        'class Outer:\n    """Outer."""\n'
        '    class Inner:\n        """Inner with value."""\n'
        '        def __init__(self):\n'
        '            """Set value."""\n'
        '            self.value = 1\n',
        encoding='utf-8',
    )
    symbols: dict[str, inventory.Symbol] = inventory.collect(package)
    assert 'sample.Outer.Inner.value' in symbols
    assert 'sample.Outer.value' not in symbols
