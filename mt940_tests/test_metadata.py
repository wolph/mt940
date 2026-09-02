import importlib
import importlib.metadata

import pytest
from mt940 import __about__


@pytest.mark.parametrize(
    ('attribute', 'contains'),
    [
        ('__title__', 'MT940'),
        ('__package_name__', 'mt-940'),
        ('__author__', 'Rick van Hattem (wolph)'),
        ('__description__', 'MT940'),
        ('__email__', '@'),
        ('__version__', '.'),
        ('__license__', 'BSD'),
        ('__copyright__', 'Rick van Hattem (wolph)'),
        ('__url__', 'https://'),
    ],
)
def test_metadata(attribute: str, contains: str) -> None:
    value: str = getattr(__about__, attribute)
    assert contains in value


def test_version_falls_back_when_the_package_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # __about__ reads the version from the installed metadata at import time.
    # A source checkout that was never installed has no metadata, and the
    # placeholder must not crash the import.
    installed = __about__.__version__

    def missing(distribution_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(distribution_name)

    monkeypatch.setattr(importlib.metadata, 'version', missing)
    try:
        assert importlib.reload(__about__).__version__ == '0.0.0'
    finally:
        monkeypatch.undo()
        _ = importlib.reload(__about__)

    assert __about__.__version__ == installed
