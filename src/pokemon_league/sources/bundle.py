"""Verification of a self-contained catalog, ledger, and content-addressed blob set."""

from __future__ import annotations

import json
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
    """Strictly parse either the canonical records envelope or a legacy bare list."""
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    values = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(values, list):
        raise TypeError("source ledger records must be a JSON array")
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
    root = sources_root.resolve(strict=False)
    blob_root = root / "blobs"
    for record in records:
        declared = Path(record.blob_path)
        expected = blob_root / record.sha256
        if declared.is_symlink() or _has_symlink_component(expected.parent, root):
            raise ValueError(f"symlink blob_path for source_id: {record.source_id}")
        if declared.resolve(strict=False) != expected.resolve(strict=False):
            raise ValueError(
                f"unexpected blob_path for source_id: {record.source_id}; "
                f"expected {expected}"
            )


def _has_symlink_component(path: Path, root: Path) -> bool:
    current = path
    while current != root:
        if current.is_symlink():
            return True
        if current.parent == current:
            return True
        current = current.parent
    return root.is_symlink()
