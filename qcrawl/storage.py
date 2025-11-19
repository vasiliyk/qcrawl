from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path


class Storage:
    """Abstract base class for storage backends."""

    def __init__(self, uri: str):
        """Initialize the storage backend.

        Args:
            uri (str): Storage URI or identifier.
        """
        self.uri = uri

    async def write(self, data: bytes, path: str) -> None:
        """Write bytes to the given path asynchronously.

        Args:
            data (bytes): Data to write.
            path (str): Relative path to write to.
        """
        raise NotImplementedError

    async def read(self, path: str) -> bytes:
        """Read bytes from the given path asynchronously.

        Args:
            path (str): Relative path to read from.

        Returns:
            bytes: Data read from the path.
        """
        raise NotImplementedError

    async def exists(self, path: str) -> bool:
        """Check asynchronously if the given path exists.

        Args:
            path (str): Relative path to check.

        Returns:
            bool: True if the path exists, False otherwise.
        """
        raise NotImplementedError

    async def close(self) -> None:
        """Close the storage and release resources asynchronously."""
        raise NotImplementedError


@dataclass
class FileStorage(Storage):
    """Local filesystem storage implementation.

    Attributes:
        root (Path): Root directory for file storage.

    Methods:
        write(data: bytes, path: str) -> None
            Asynchronously append bytes to a file at the given path.
        read(path: str) -> bytes
            Asynchronously read bytes from a file at the given path.
        exists(path: str) -> bool
            Asynchronously check if a file exists at the given path.
        close() -> None
            Asynchronously close the storage (no-op for local files).
    """

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def write(self, data: bytes, path: str) -> None:
        abs_path = self.root / path
        await asyncio.to_thread(self._append_bytes_sync, abs_path, data)

    def _append_bytes_sync(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "ab") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

    async def read(self, path: str) -> bytes:
        abs_path = self.root / path
        return await asyncio.to_thread(self._read_bytes_sync, abs_path)

    def _read_bytes_sync(self, path: Path) -> bytes:
        with open(path, "rb") as f:
            return f.read()

    async def exists(self, path: str) -> bool:
        abs_path = self.root / path
        return await asyncio.to_thread(abs_path.exists)

    async def close(self) -> None:
        return None
