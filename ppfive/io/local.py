from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

from .bytereader import ByteReader
from .mock_filesystem import MockFilesystem


class LocalPosixReader(ByteReader):
    """POSIX file reader using pread-style absolute reads."""

    def __init__(
        self, path: str | os.PathLike[str], local_os_cache: bool = True
    ):
        """TODO."""
        self.path = str(Path(path))
        self._fd = os.open(self.path, os.O_RDONLY)
        self._local_os_cache = local_os_cache
        self._set_cache_policy()

        # Create a mock file system with selected attributes
        self.fs = MockFilesystem(protocol="file")
        
    def _set_cache_policy(self) -> None:
        """TODO."""
        # Best effort hint for benchmarking without page cache on macOS.
        if self._local_os_cache:
            return

        try:
            import fcntl
        except ImportError:
            return

        if hasattr(fcntl, "F_NOCACHE"):
            try:
                fcntl.fcntl(self._fd, fcntl.F_NOCACHE, 1)
            except OSError:
                # Cache hint is optional; do not fail reads if unsupported.
                pass

    @staticmethod
    def drop_os_cache_best_effort() -> bool:
        """Best-effort cache drop for local benchmarking.

        On macOS this tries the `purge` command when available.
        Returns True when a cache-drop command was executed successfully.

        """
        if platform.system() == "Darwin" and shutil.which("purge"):
            try:
                completed = subprocess.run(
                    ["purge"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return completed.returncode == 0
            except OSError:
                return False

        return False

    def read_at(self, offset: int, nbytes: int) -> bytes:
        """TODO."""
        if offset < 0:
            raise ValueError("offset must be >= 0")
        
        if nbytes < 0:
            raise ValueError("nbytes must be >= 0")

        if self._fd is None:
            self._fd = os.open(self.path, os.O_RDONLY)
            self._set_cache_policy()

        return os.pread(self._fd, nbytes, offset)

    def close(self) -> None:
        """TODO."""
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
