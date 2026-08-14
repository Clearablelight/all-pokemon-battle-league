"""Offline validation for source provenance ledgers."""

import argparse
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from pokemon_league.sources.snapshot import SourceRecord, _file_digest_and_size

DEFAULT_CUTOFF = date(2026, 8, 14)


def validate_source_ledger(
    records: Sequence[SourceRecord], *, cutoff: date = DEFAULT_CUTOFF
) -> tuple[str, ...]:
    """Validate local source evidence and return optional sources still uncovered."""
    seen: set[str] = set()
    coverage_gaps: list[str] = []
    for record in records:
        if record.source_id in seen:
            raise ValueError(f"duplicate source_id: {record.source_id}")
        seen.add(record.source_id)
        if not record.continuity_id.strip():
            raise ValueError(f"blank continuity_id for source_id: {record.source_id}")
        if record.publication_date is not None and record.publication_date > cutoff:
            raise ValueError(
                f"publication_date after cutoff for source_id: {record.source_id}"
            )

        blob = Path(record.blob_path)
        if not blob.is_file():
            if record.required:
                raise ValueError(
                    f"missing required blob for source_id: {record.source_id}"
                )
            coverage_gaps.append(record.source_id)
            continue
        actual_digest, actual_size = _file_digest_and_size(blob)
        if actual_digest != record.sha256:
            raise ValueError(f"sha256 mismatch for source_id: {record.source_id}")
        if actual_size != record.byte_count:
            raise ValueError(f"byte_count mismatch for source_id: {record.source_id}")
    return tuple(sorted(coverage_gaps))


def _load_ledger(path: Path) -> tuple[SourceRecord, ...]:
    """Load records from either a bare JSON array or its records envelope."""
    if not path.exists():
        return ()
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    values = payload["records"] if isinstance(payload, dict) else payload
    if not isinstance(values, list):
        raise TypeError("ledger records must be a JSON array")
    return tuple(SourceRecord.model_validate(value) for value in values)


def _catalog_source_ids(path: Path) -> tuple[str, ...]:
    """Read source IDs from the local YAML catalog without contacting its URLs."""
    payload: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    values = payload.get("sources", []) if isinstance(payload, dict) else []
    if not isinstance(values, list):
        raise TypeError("sources catalog must contain a sources list")
    return tuple(str(value["source_id"]) for value in values)


def main(argv: Sequence[str] | None = None) -> int:
    """Validate a local ledger; offline mode never performs source fetching."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    arguments = parser.parse_args(argv)
    if not arguments.offline:
        parser.error("only --offline validation is supported")

    try:
        records = _load_ledger(arguments.ledger)
        unsnapshotted_records = {
            record.source_id
            for record in records
            if not Path(record.blob_path).is_file()
        }
        gaps = validate_source_ledger(
            tuple(
                record
                for record in records
                if record.source_id not in unsnapshotted_records
            )
        )
        known_ids = {record.source_id for record in records}
        missing = sorted(
            (set(_catalog_source_ids(Path("config/sources.yaml"))) - known_ids)
            | set(gaps)
            | unsnapshotted_records
        )
    except (
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        yaml.YAMLError,
    ) as error:
        print(str(error), file=__import__("sys").stderr)
        return 2

    if missing:
        print(
            f"missing or unsnapshotted source IDs: {', '.join(missing)}",
            file=__import__("sys").stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
