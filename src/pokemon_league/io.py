"""Deterministic, atomic writers for generated battle-league artifacts."""

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd  # type: ignore[import-untyped]


def _temporary_sibling(path: Path) -> Path:
    """Allocate an unpublished temporary path beside its final destination."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        return Path(handle.name)


def _fsync_then_replace(temporary_path: Path, final_path: Path) -> None:
    """Durably flush a sibling temporary file before atomically replacing final_path."""
    descriptor = os.open(temporary_path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary_path, final_path)


def _write_atomically(path: Path, writer: Callable[[Path], None]) -> str:
    """Write final bytes with a sibling temporary file and return their SHA-256."""
    temporary_path = _temporary_sibling(path)
    try:
        writer(temporary_path)
        _fsync_then_replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_atomic(path: Path, value: object) -> str:
    """Write canonical JSON atomically and return the final content hash."""

    def write(temporary_path: Path) -> None:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

    return _write_atomically(path, write)


def write_table_atomic(
    frame: pd.DataFrame,
    parquet_path: Path,
    csv_path: Path | None = None,
) -> dict[str, str]:
    """Write deterministic Zstandard Parquet and optional UTF-8 CSV atomically."""
    if csv_path is not None and parquet_path.resolve(strict=False) == csv_path.resolve(
        strict=False
    ):
        raise ValueError("parquet_path and csv_path must be distinct destinations")

    def write_parquet(temporary_path: Path) -> None:
        frame.to_parquet(
            temporary_path,
            engine="pyarrow",
            compression="zstd",
            index=False,
        )

    digests = {"parquet": _write_atomically(parquet_path, write_parquet)}
    if csv_path is not None:

        def write_csv(temporary_path: Path) -> None:
            frame.to_csv(
                temporary_path,
                encoding="utf-8",
                index=False,
                lineterminator="\n",
            )

        digests["csv"] = _write_atomically(csv_path, write_csv)
    return digests
