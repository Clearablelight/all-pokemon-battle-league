"""Stable one-descriptor capture for parsed and audited local inputs."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

READ_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class CapturedFile:
    """Immutable bytes and identity computed during the same descriptor read."""

    path: Path
    data: bytes
    sha256: str
    byte_count: int


def capture_regular_file(path: Path) -> CapturedFile:
    """Read one regular file without following any lexical symlink component."""
    descriptor = _open_regular_nofollow(path)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"unsafe regular input: {path}")
        data = _read_descriptor(descriptor)
        after = os.fstat(descriptor)
        if _stat_fingerprint(before) != _stat_fingerprint(after):
            raise ValueError(f"input changed while being captured: {path}")
        if len(data) != after.st_size:
            raise ValueError(f"input changed while being captured: {path}")
    finally:
        os.close(descriptor)
    return CapturedFile(
        path=path,
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
        byte_count=len(data),
    )


def _open_regular_nofollow(path: Path) -> int:
    """Traverse from the filesystem root through no-follow directory descriptors."""
    absolute = path if path.is_absolute() else Path.cwd() / path
    parts = absolute.parts
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    cloexec = getattr(os, "O_CLOEXEC", 0)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | nofollow | cloexec
    file_flags = os.O_RDONLY | nofollow | cloexec
    if len(parts) == 1:
        try:
            return os.open(absolute, file_flags)
        except FileNotFoundError:
            raise
        except OSError as error:
            raise ValueError(f"unsafe regular input: {path}") from error

    directory_descriptor: int | None = None
    try:
        directory_descriptor = os.open(parts[0], directory_flags)
        for component in parts[1:-1]:
            next_descriptor = os.open(
                component,
                directory_flags,
                dir_fd=directory_descriptor,
            )
            os.close(directory_descriptor)
            directory_descriptor = next_descriptor
        return os.open(parts[-1], file_flags, dir_fd=directory_descriptor)
    except FileNotFoundError:
        raise
    except OSError as error:
        raise ValueError(f"unsafe regular input: {path}") from error
    finally:
        if directory_descriptor is not None:
            os.close(directory_descriptor)


def _read_descriptor(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    while chunk := os.read(descriptor, READ_CHUNK_BYTES):
        chunks.append(chunk)
    return b"".join(chunks)


def _stat_fingerprint(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )
