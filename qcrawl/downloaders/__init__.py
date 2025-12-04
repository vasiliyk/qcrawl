"""Pluggable downloader implementations for qcrawl.

This package provides different downloader backends:
- HTTPDownloader: Fast aiohttp-based downloader (default)
- CamoufoxDownloader: Stealth browser-based downloader for JS-heavy sites
- DownloadHandlerManager: Routes requests to appropriate downloaders
"""

from qcrawl.downloaders.base import DownloaderProtocol
from qcrawl.downloaders.handler_manager import DownloadHandlerManager
from qcrawl.downloaders.http import HTTPDownloader

__all__ = ["DownloaderProtocol", "HTTPDownloader", "DownloadHandlerManager"]

# Camoufox downloader is optional (requires camoufox package)
try:
    from qcrawl.downloaders.camoufox import CamoufoxDownloader  # noqa: F401

    __all__.append("CamoufoxDownloader")
except ImportError:
    # Camoufox not installed - skip optional downloader
    pass
