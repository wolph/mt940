"""Package metadata, with the version single-sourced from the distribution."""

from importlib.metadata import (
    PackageNotFoundError,
    version as _version,
)

#: Display name of the library.
__title__ = 'MT940'
#: Distribution name used by package installers and installed metadata.
__package_name__ = 'mt-940'
#: Original author and maintainer attribution.
__author__ = 'Rick van Hattem (wolph)'
#: Short distribution summary retained for compatibility.
__description__ = (
    'A library to parse MT940 files and returns smart Python collections for '
    'statistics and manipulation.'
)
#: Maintainer contact address.
__email__ = 'wolph@wol.ph'
#: Historical short licence label. See LICENSE for the full terms.
__license__ = 'BSD'
#: Original copyright attribution.
__copyright__ = 'Copyright 2015 Rick van Hattem (wolph)'
#: Canonical source repository URL.
__url__ = 'https://github.com/WoLpH/mt940'

# The version is single-sourced from the installed package metadata
# (pyproject.toml).
#: Installed distribution version, or 0.0.0 when metadata is unavailable.
__version__: str
try:
    __version__ = _version('mt-940')
except PackageNotFoundError:
    __version__ = '0.0.0'
