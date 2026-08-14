"""Verification of a self-contained catalog, ledger, and content-addressed blob set."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from pokemon_league.sources.catalog import load_source_catalog
from pokemon_league.sources.snapshot import SourceRecord
from pokemon_league.sources.validate import validate_source_ledger


@dataclass(frozen=True)
class VerifiedSourceBundle:
    """Locally verified records and their non-blocking optional coverage gaps."""

    records: tuple[SourceRecord, ...]
    coverage_gaps: tuple[str, ...]
    verified_source_ids: frozenset[str]


def load_source_ledger(path: Path) -> tuple[SourceRecord, ...]:
    """Strictly parse the canonical publication ledger envelope."""
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != {"records"}:
        raise ValueError("source ledger must use the exact records envelope")
    values = payload["records"]
    if not isinstance(values, list):
        raise TypeError("source ledger exact records envelope must contain an array")
    return tuple(SourceRecord.model_validate(value) for value in values)


def verify_source_bundle(
    sources_root: Path,
    ledger_path: Path,
    catalog_path: Path,
    cutoff: date,
) -> VerifiedSourceBundle:
    """Verify exact blob placement, catalog coverage, checksums, and sizes offline."""
    specs = load_source_catalog(catalog_path)
    records = load_source_ledger(ledger_path)
    _validate_blob_identities(sources_root, records)
    record_coverage_gaps = set(validate_source_ledger(records, cutoff=cutoff))
    catalog_by_id = {spec.source_id: spec for spec in specs}
    record_by_id = {record.source_id: record for record in records}

    unknown_ledger_ids = sorted(set(record_by_id) - set(catalog_by_id))
    if unknown_ledger_ids:
        raise ValueError(f"unknown ledger source IDs: {', '.join(unknown_ledger_ids)}")
    missing_required = sorted(
        source_id
        for source_id, spec in catalog_by_id.items()
        if spec.required and source_id not in record_by_id
    )
    if missing_required:
        raise ValueError(
            f"missing required catalog source IDs: {', '.join(missing_required)}"
        )
    coverage_gaps = tuple(
        sorted(
            record_coverage_gaps
            | {
                source_id
                for source_id, spec in catalog_by_id.items()
                if not spec.required and source_id not in record_by_id
            }
        )
    )
    verified = frozenset(
        record.source_id
        for record in records
        if record.source_id not in coverage_gaps
    )
    missing_required_verification = sorted(
        source_id
        for source_id, spec in catalog_by_id.items()
        if spec.required and source_id not in verified
    )
    if missing_required_verification:
        raise ValueError(
            "unverified required catalog source IDs: "
            + ", ".join(missing_required_verification)
        )
    return VerifiedSourceBundle(records, coverage_gaps, verified)


def _validate_blob_identities(
    sources_root: Path, records: tuple[SourceRecord, ...]
) -> None:
    anchored_root = _anchor_lexically(sources_root)
    if _has_lexical_symlink_component(anchored_root):
        raise ValueError(f"symlink sources root: {sources_root}")
    root = Path(os.path.abspath(sources_root)).resolve(strict=False)
    blob_root = root / "blobs"
    for record in records:
        anchored_declared = _anchor_lexically(Path(record.blob_path))
        declared = Path(os.path.abspath(record.blob_path))
        expected = blob_root / record.sha256
        if _has_lexical_symlink_component(anchored_declared):
            raise ValueError(f"symlink blob_path for source_id: {record.source_id}")
        if declared.resolve(strict=False) != expected.resolve(strict=False):
            raise ValueError(
                f"unexpected blob_path for source_id: {record.source_id}; "
                f"expected {expected}"
            )
        _assert_regular_nofollow(declared, record.source_id)


def _has_lexical_symlink_component(path: Path) -> bool:
    """Inspect every existing lexical component without resolving links."""
    anchored = _anchor_lexically(path)
    current = Path(anchored.anchor)
    for part in anchored.parts[1:]:
        if part == "..":
            current = current.parent
            continue
        current /= part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode):
            return True
    return False


def _anchor_lexically(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def _assert_regular_nofollow(path: Path, source_id: str) -> None:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return
    except OSError as error:
        raise ValueError(f"unsafe blob_path for source_id: {source_id}") from error
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError(f"unsafe blob_path for source_id: {source_id}")
    finally:
        os.close(descriptor)
