import pytest


@pytest.mark.parametrize('attribute,contains', [
    ('__package_name__', ''),
    ('__version__', ''),
    ('__author__', ''),
    ('__author_email__', '@'),
    ('__description__', ''),
    ('__url__', 'https://'),
])
def test_metadata(attribute, contains):
    from mt940 import metadata
    assert getattr(metadata, attribute)
    if contains:
        assert contains in getattr(metadata, attribute)

