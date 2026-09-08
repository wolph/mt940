"""Check the reviewed documentation inventory against source and HTML."""

from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from typing import TypedDict, cast

from .symbols import Symbol, collect

__all__: list[str] = [
    'Record',
    'Symbol',
    'check_rendered',
    'check_source',
    'collect',
    'read_manifest',
]


class Record(TypedDict):
    """Reviewed reference, guides and tests for one package module."""

    reference: str
    guides: list[str]
    tests: list[str]
    symbols: list[str]


def read_manifest(path: Path) -> dict[str, Record]:
    """Validate the JSON inventory before using its paths or symbol names.

    Returns:
        Module records containing a reference page, guides, tests and symbols.

    Raises:
        TypeError: When a record has an invalid field type.
    """
    raw: object = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw, dict):
        message: str = 'inventory must be a module mapping'
        raise TypeError(message)
    mapping: dict[object, object] = cast('dict[object, object]', raw)
    for module, record in mapping.items():
        if not isinstance(module, str) or not isinstance(record, dict):
            message = 'inventory modules must map names to records'
            raise TypeError(message)
        fields: dict[object, object] = cast('dict[object, object]', record)
        if not isinstance(fields.get('reference'), str):
            message = f'{module}: reference must be a string'
            raise TypeError(message)
        for key in ('guides', 'tests', 'symbols'):
            values: object = fields.get(key)
            if not isinstance(values, list) or not all(
                isinstance(item, str) for item in cast('list[object]', values)
            ):
                message = f'{module}: {key} must be a list of strings'
                raise TypeError(message)
    return cast('dict[str, Record]', raw)


def check_source(package: Path, manifest: Path) -> list[str]:
    """Report undocumented, newly added and removed source definitions.

    Returns:
        Validation errors, or an empty list when the inventory matches.
    """
    symbols: dict[str, Symbol] = collect(package)
    records: dict[str, Record] = read_manifest(manifest)
    listed: list[str] = [
        name for record in records.values() for name in record['symbols']
    ]
    errors: list[str] = []
    errors.extend(
        f'unlisted symbol: {name}'
        for name in sorted(symbols.keys() - set(listed))
    )
    errors.extend(
        f'stale symbol: {name}'
        for name in sorted(set(listed) - symbols.keys())
    )
    if len(listed) != len(set(listed)):
        errors.append('duplicate inventory entries')
    for name, symbol in symbols.items():
        if not symbol.documented:
            errors.append(f'missing docstring: {name}')
    for module, record in records.items():
        errors.extend(
            f'{module}: missing test file: {test}'
            for test in record['tests']
            if not (package.parent / test).is_file()
        )
    return errors


class _Anchors(HTMLParser):
    """Collect actual HTML IDs without guessing from reference text."""

    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        """Record each element ID."""
        _ = tag
        self.ids.update(value for key, value in attrs if key == 'id' and value)
        self.ids.update(
            value.removeprefix('module-')
            for key, value in attrs
            if key == 'id' and value and value.startswith('module-')
        )


def check_rendered(
    symbols: dict[str, Symbol], records: dict[str, Record], html: Path
) -> list[str]:
    """Report missing guide pages and canonical reference anchors.

    Returns:
        Missing reference, guide and anchor descriptions.
    """
    errors: list[str] = []
    anchors: set[str] = set()
    for record in records.values():
        reference: Path = html / record['reference']
        if reference.is_file():
            parser: _Anchors = _Anchors()
            parser.feed(reference.read_text(encoding='utf-8'))
            anchors.update(parser.ids)
        else:
            errors.append(f'missing reference: {record["reference"]}')
        errors.extend(
            f'missing guide: {guide}'
            for guide in record['guides']
            if not (html / guide).is_file()
        )
    for name, symbol in symbols.items():
        if symbol.anchor not in anchors:
            errors.append(
                f'missing reference anchor: {name} ({symbol.anchor})'
            )
    return errors


def main() -> int:
    """Check the source inventory and, optionally, a completed HTML build.

    Returns:
        Zero on success or one when validation finds errors.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=__doc__
    )
    _ = parser.add_argument('--html', type=Path)
    arguments: argparse.Namespace = parser.parse_args()
    root: Path = Path(__file__).resolve().parents[2]
    manifest: Path = root / 'docs' / 'inventory.json'
    errors: list[str] = check_source(root / 'mt940', manifest)
    if arguments.html:
        errors.extend(
            check_rendered(
                collect(root / 'mt940'),
                read_manifest(manifest),
                arguments.html,
            )
        )
    for error in errors:
        print(error)
    if not errors:
        count: int = len(collect(root / 'mt940'))
        print(f'Documentation inventory: {count} symbols checked')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
