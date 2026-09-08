"""Validate local links, fragments and assets in a Sphinx HTML build."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import SplitResult, unquote, urlsplit


class _Page(HTMLParser):
    """Collect a page's link targets and referenced URLs."""

    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.urls: set[str] = set()

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        """Read IDs, legacy anchor names, links and asset sources."""
        for name, value in attrs:
            if value is None:
                continue
            if name == 'id' or (tag == 'a' and name == 'name'):
                self.ids.add(value)
            elif name in {'href', 'src'}:
                self.urls.add(value)


def _target(root: Path, source: Path, url: str) -> tuple[Path, str] | None:
    """Resolve local URLs while leaving remote and non-file schemes alone.

    Returns:
        A destination and fragment, or None for an external URL.
    """
    parsed: SplitResult = urlsplit(url)
    if parsed.scheme or parsed.netloc:
        return None
    path: str = unquote(parsed.path)
    target: Path = (
        (
            root / path.lstrip('/')
            if path.startswith('/')
            else source.parent / path
        )
        if path
        else source
    )
    if target.is_dir():
        target /= 'index.html'
    return target.resolve(), unquote(parsed.fragment)


def check(root: Path) -> list[str]:
    """Report unresolved local URLs in generated HTML.

    Returns:
        Missing files and fragments, or an empty list for a valid build.
    """
    root = root.resolve()
    pages: dict[Path, _Page] = {}
    for path in sorted(root.rglob('*.html')):
        page: _Page = _Page()
        page.feed(path.read_text(encoding='utf-8'))
        pages[path] = page
    errors: list[str] = []
    for path, page in pages.items():
        for url in sorted(page.urls):
            target: tuple[Path, str] | None = _target(root, path, url)
            if target is None:
                continue
            destination, fragment = target
            if (
                not destination.is_relative_to(root)
                or not destination.is_file()
            ):
                errors.append(f'{path.relative_to(root)}: missing file: {url}')
            elif (
                fragment
                and destination in pages
                and fragment not in pages[destination].ids
            ):
                errors.append(
                    f'{path.relative_to(root)}: missing fragment: {url}'
                )
    return errors


def main() -> int:
    """Check a completed build for broken local links.

    Returns:
        Zero for a valid build or one when links are broken.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=__doc__
    )
    _ = parser.add_argument('html', type=Path)
    arguments: argparse.Namespace = parser.parse_args()
    errors: list[str] = check(arguments.html)
    for error in errors:
        print(error)
    if not errors:
        print('Local documentation links: all targets exist')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
