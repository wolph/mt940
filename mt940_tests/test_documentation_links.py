"""Catch missing files and fragments in generated documentation."""

from pathlib import Path

from docs._tools import links


def test_links_check_images_pages_and_decoded_fragments(
    tmp_path: Path,
) -> None:
    (tmp_path / 'index.html').write_text(
        '<a href="guide.html#part%20one">Guide</a>'
        '<a href="https://example.org/">External</a>'
        '<a href="mailto:example@example.org">Email</a>'
        '<img src="missing.svg">',
        encoding='utf-8',
    )
    (tmp_path / 'guide.html').write_text(
        '<h1 id="part one">Guide</h1>', encoding='utf-8'
    )
    errors: list[str] = links.check(tmp_path)
    assert len(errors) == 1
    assert 'missing.svg' in errors[0]
    (tmp_path / 'missing.svg').write_text('<svg/>', encoding='utf-8')
    assert links.check(tmp_path) == []


def test_links_report_missing_fragments_and_escaping_paths(
    tmp_path: Path,
) -> None:
    (tmp_path / 'index.html').write_text(
        '<a href="#absent">Missing</a><a href="../outside.html">Outside</a>',
        encoding='utf-8',
    )
    errors: list[str] = links.check(tmp_path)
    assert any('#absent' in error for error in errors)
    assert any('../outside.html' in error for error in errors)
