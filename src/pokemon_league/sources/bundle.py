"""Verification of a self-contained catalog, ledger, and content-addressed blob set."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from pokemon_league.input_capture import CapturedFile, capture_regular_file
from pokemon_league.sources.catalog import parse_source_catalog
from pokemon_league.sources.snapshot import SourceRecord

CATALOG_BOUND_FIELDS = (
    "url",
    "source_kind",
    "continuity_id",
    "required",
    "license_note",
    "publication_date",
)


@dataclass(frozen=True)
class VerifiedSourceBundle:
    """Locally verified records and their non-blocking optional coverage gaps."""

    records: tuple[SourceRecord, ...]
    coverage_gaps: tuple[str, ...]
    verified_source_ids: frozenset[str]
    verified_blob_hashes: tuple[tuple[str, str], ...]


def load_source_ledger(path: Path) -> tuple[SourceRecord, ...]:
    """Strictly parse the canonical publication ledger envelope."""
    return parse_source_ledger(capture_regular_file(path).data)


def parse_source_ledger(data: bytes) -> tuple[SourceRecord, ...]:
    """Strictly parse a canonical ledger from exact captured bytes."""
    payload: Any = json.loads(data.decode("utf-8"))
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
    ledger = capture_regular_file(ledger_path)
    catalog = capture_regular_file(catalog_path)
    return verify_captured_source_bundle(sources_root, ledger, catalog, cutoff)


def verify_captured_source_bundle(
    sources_root: Path,
    ledger: CapturedFile,
    catalog: CapturedFile,
    cutoff: date,
) -> VerifiedSourceBundle:
    """Verify a source bundle using the exact captured catalog and ledger bytes."""
    specs = parse_source_catalog(catalog.data)
    records = parse_source_ledger(ledger.data)
    _validate_record_metadata(records, cutoff)
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
    for record in records:
        spec = catalog_by_id[record.source_id]
        for field in CATALOG_BOUND_FIELDS:
            if getattr(record, field) != getattr(spec, field):
                raise ValueError(
                    f"source metadata mismatch for {record.source_id}: {field}"
                )

    record_coverage_gaps, verified_blob_hashes = _validate_blob_identities(
        sources_root, records
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
    return VerifiedSourceBundle(
        records,
        coverage_gaps,
        verified,
        tuple(
            (source_id, digest)
            for source_id, digest in verified_blob_hashes
            if source_id in verified
        ),
    )


def _validate_record_metadata(records: tuple[SourceRecord, ...], cutoff: date) -> None:
    seen: set[str] = set()
    for record in records:
        if record.source_id in seen:
            raise ValueError(f"duplicate source_id: {record.source_id}")
        seen.add(record.source_id)
        if record.publication_date is not None and record.publication_date > cutoff:
            raise ValueError(
                f"publication_date after cutoff for source_id: {record.source_id}"
            )


def _validate_blob_identities(
    sources_root: Path, records: tuple[SourceRecord, ...]
) -> tuple[set[str], tuple[tuple[str, str], ...]]:
    anchored_root = _anchor_lexically(sources_root)
    if _has_lexical_symlink_component(anchored_root):
        raise ValueError(f"symlink sources root: {sources_root}")
    root = Path(os.path.abspath(sources_root)).resolve(strict=False)
    blob_root = root / "blobs"
    coverage_gaps: set[str] = set()
    verified_hashes: list[tuple[str, str]] = []
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
        try:
            captured = capture_regular_file(declared)
        except FileNotFoundError:
            if record.required:
                raise ValueError(
                    f"missing required blob for source_id: {record.source_id}"
                ) from None
            coverage_gaps.add(record.source_id)
            continue
        except ValueError as error:
            raise ValueError(
                f"unsafe blob_path for source_id: {record.source_id}"
            ) from error
        if captured.sha256 != record.sha256:
            raise ValueError(f"sha256 mismatch for source_id: {record.source_id}")
        if captured.byte_count != record.byte_count:
            raise ValueError(f"byte_count mismatch for source_id: {record.source_id}")
        verified_hashes.append((record.source_id, captured.sha256))
    return coverage_gaps, tuple(sorted(verified_hashes))


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
