"""Package metadata, with the version single-sourced from the distribution."""

from importlib.metadata import (
    PackageNotFoundError,
    version as _version,
)

__title__ = 'MT940'
__package_name__ = 'mt-940'
__author__ = 'Rick van Hattem (wolph)'
__description__ = (
    'A library to parse MT940 files and returns smart Python collections for '
    'statistics and manipulation.'
)
__email__ = 'wolph@wol.ph'
__license__ = 'BSD'
__copyright__ = 'Copyright 2015 Rick van Hattem (wolph)'
__url__ = 'https://github.com/WoLpH/mt940'

# The version is single-sourced from the installed package metadata
# (pyproject.toml).
__version__: str
try:
    __version__ = _version('mt-940')
except PackageNotFoundError:
    __version__ = '0.0.0'
