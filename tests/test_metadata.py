import pytest


@pytest.mark.parametrize('attribute,contains', [
    ('__title__', 'MT940'),
    ('__package_name__', 'mt-940'),
    ('__author__', 'Rick van Hattem (wolph)'),
    ('__description__', 'MT940'),
    ('__email__', '@'),
    ('__version__', '.'),
    ('__license__', 'BSD'),
    ('__copyright__', 'Rick van Hattem (wolph)'),
    ('__url__', 'https://'),
])
def test_metadata(attribute, contains):
    from mt940 import __about__
    assert getattr(__about__, attribute)
    if contains:
        assert contains in getattr(__about__, attribute)

