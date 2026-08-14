"""Command-line source snapshot, verification, and roster publication pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Any

import pandas as pd  # type: ignore[import-untyped]
import typer
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from pokemon_league.config import load_run_config
from pokemon_league.io import write_csv_atomic, write_json_atomic, write_table_atomic
from pokemon_league.roster.builder import build_roster
from pokemon_league.roster.equivalence import canonicalize_tracks
from pokemon_league.roster.evolution import assign_evolution_metadata
from pokemon_league.roster.loader import load_form_decisions_csv
from pokemon_league.roster.validate import RosterAudit, validate_roster
from pokemon_league.schemas.roster import (
    Combatant,
    EvolutionEdge,
    ExcludedForm,
    RawForm,
)
from pokemon_league.sources.snapshot import (
    SourceRecord,
    SourceSpec,
    fetch_https_bytes,
    snapshot_sources,
)
from pokemon_league.sources.validate import validate_source_ledger

app = typer.Typer(help="Build the audited all-Pokémon battle-league roster.")
sources_app = typer.Typer(help="Snapshot and verify immutable source evidence.")
roster_app = typer.Typer(help="Build and publish the validated contestant roster.")
app.add_typer(sources_app, name="sources")
app.add_typer(roster_app, name="roster")

Fetch = Callable[[str], bytes]


def _utc_now() -> datetime:
    """Return the injectable source retrieval timestamp."""
    return datetime.now(UTC)


def _fail(error: BaseException | str) -> None:
    typer.echo(str(error), err=True)
    raise typer.Exit(code=2)


def _load_catalog(path: Path) -> tuple[SourceSpec, ...]:
    """Strictly parse SourceSpec fields while allowing documented pin metadata."""
    payload: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != {"sources"}:
        raise ValueError("source catalog must contain only a sources list")
    values = payload["sources"]
    if not isinstance(values, list):
        raise TypeError("source catalog sources must be a list")
    allowed = set(SourceSpec.model_fields)
    specs: list[SourceSpec] = []
    for index, value in enumerate(values):
        if not isinstance(value, dict):
            raise TypeError(f"source catalog row {index + 1} must be an object")
        selected = {key: item for key, item in value.items() if key in allowed}
        specs.append(SourceSpec.model_validate(selected))
    identifiers = [spec.source_id for spec in specs]
    duplicates = sorted(
        identifier
        for identifier in set(identifiers)
        if identifiers.count(identifier) > 1
    )
    if duplicates:
        raise ValueError(f"duplicate catalog source_id: {duplicates[0]}")
    return tuple(sorted(specs, key=lambda spec: spec.source_id))


def _ledger_payload(records: Sequence[SourceRecord]) -> dict[str, object]:
    return {
        "records": [record.model_dump(mode="json") for record in records],
    }


@sources_app.command("snapshot")
def sources_snapshot(
    catalog: Annotated[Path, typer.Option("--catalog")] = Path("config/sources.yaml"),
    output: Annotated[Path, typer.Option("--output")] = Path("work/sources"),
    cutoff: Annotated[str, typer.Option("--cutoff")] = "2026-08-14",
) -> None:
    """Fetch an HTTPS catalog into immutable blobs and an atomic sorted ledger."""
    try:
        cutoff_date = date.fromisoformat(cutoff)
        specs = _load_catalog(catalog)
        for spec in specs:
            if (
                spec.publication_date is not None
                and spec.publication_date > cutoff_date
            ):
                raise ValueError(
                    f"publication_date after cutoff for source_id: {spec.source_id}"
                )
        records = snapshot_sources(specs, output, _utc_now(), fetch_https_bytes)
        validate_source_ledger(records, cutoff=cutoff_date)
        write_json_atomic(output / "source-ledger.json", _ledger_payload(records))
    except (OSError, TypeError, ValueError, ValidationError, yaml.YAMLError) as error:
        _fail(error)


def _load_ledger(path: Path) -> tuple[SourceRecord, ...]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    values = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(values, list):
        raise TypeError("source ledger records must be a JSON array")
    return tuple(SourceRecord.model_validate(value) for value in values)


def _verify_sources(
    ledger_path: Path, catalog_path: Path, cutoff: date
) -> tuple[tuple[SourceRecord, ...], tuple[str, ...], set[str]]:
    specs = _load_catalog(catalog_path)
    records = _load_ledger(ledger_path)
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
    verified = {
        record.source_id
        for record in records
        if record.source_id not in coverage_gaps and Path(record.blob_path).is_file()
    }
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
    return records, coverage_gaps, verified


@sources_app.command("verify")
def sources_verify(
    ledger: Annotated[Path, typer.Option("--ledger")],
    catalog: Annotated[Path, typer.Option("--catalog")] = Path("config/sources.yaml"),
    offline: Annotated[bool, typer.Option("--offline")] = False,
    cutoff: Annotated[str, typer.Option("--cutoff")] = "2026-08-14",
) -> None:
    """Verify ledger/blob hashes locally; offline mode performs no network work."""
    if not offline:
        _fail("sources verify requires --offline")
    try:
        _verify_sources(ledger, catalog, date.fromisoformat(cutoff))
    except Exception as error:  # noqa: BLE001 - stable CLI error boundary
        _fail(error)


def _load_raw_forms(path: Path) -> tuple[RawForm, ...]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError("raw forms must be a JSON array")
    return tuple(RawForm.model_validate(value) for value in payload)


def _load_evolution_edges(path: Path) -> tuple[EvolutionEdge, ...]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError("evolution edges must be a JSON array")
    return tuple(EvolutionEdge.model_validate(value) for value in payload)


def _check_source_ids(
    rows: Iterable[RawForm | EvolutionEdge | Any],
    verified_source_ids: set[str],
    kind: str,
) -> None:
    used = {source_id for row in rows for source_id in row.source_ids}
    invalid = sorted(used - verified_source_ids)
    if invalid:
        raise ValueError(
            f"unknown or unverified source IDs in {kind}: {', '.join(invalid)}"
        )


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _frame_for_models[ManifestRow: (Combatant, ExcludedForm)](
    rows: Sequence[ManifestRow], model_type: type[ManifestRow]
) -> pd.DataFrame:
    values = [row.model_dump(mode="json") for row in rows]
    return pd.DataFrame(values, columns=list(model_type.model_fields))


def _csv_frame(frame: pd.DataFrame) -> pd.DataFrame:
    exported = frame.copy()
    for column in exported.columns:
        if any(isinstance(value, (list, tuple)) for value in exported[column]):
            exported[column] = exported[column].map(
                lambda value: (
                    json.dumps(sorted(value), ensure_ascii=False, separators=(",", ":"))
                    if isinstance(value, (list, tuple))
                    else value
                )
            )
    return exported


def _publish_files(staged: dict[Path, Path]) -> None:
    """Publish a staged file set transactionally while preserving unrelated files."""
    backup_root = Path(tempfile.mkdtemp(prefix=".pokemon-league-backup-"))
    backups: dict[Path, Path] = {}
    published: list[Path] = []
    created_parents: list[Path] = []
    try:
        for index, final in enumerate(staged):
            if not final.parent.exists():
                final.parent.mkdir(parents=True)
                created_parents.append(final.parent)
            if final.exists():
                backup = backup_root / str(index)
                os.replace(final, backup)
                backups[final] = backup
        for final, source in staged.items():
            os.replace(source, final)
            published.append(final)
    except BaseException:
        for final in reversed(published):
            if final.is_file():
                final.unlink()
        for final, backup in backups.items():
            if backup.exists():
                os.replace(backup, final)
        for parent in reversed(created_parents):
            try:
                parent.rmdir()
            except OSError:
                pass
        raise
    finally:
        shutil.rmtree(backup_root, ignore_errors=True)


def _stage_and_publish(
    build,
    audit: RosterAudit,
    input_hashes: dict[str, str],
    output: Path,
    audit_path: Path,
) -> RosterAudit:
    stage_root = Path(
        tempfile.mkdtemp(prefix=".pokemon-league-stage-", dir=output.parent)
    )
    try:
        combatants = _frame_for_models(build.combatants, Combatant)
        exclusions = _frame_for_models(build.exclusions, ExcludedForm)
        parquet_stage = stage_root / "combatants.parquet"
        combatants_csv_stage = stage_root / "combatants.csv"
        exclusions_csv_stage = stage_root / "excluded-forms.csv"
        audit_stage = stage_root / "roster-audit.json"
        parquet_hash = write_table_atomic(combatants, parquet_stage)["parquet"]
        combatants_csv_hash = write_csv_atomic(
            _csv_frame(combatants), combatants_csv_stage
        )
        exclusions_csv_hash = write_csv_atomic(
            _csv_frame(exclusions), exclusions_csv_stage
        )
        output_hashes = {
            "combatants.csv": combatants_csv_hash,
            "combatants.parquet": parquet_hash,
            "excluded-forms.csv": exclusions_csv_hash,
        }
        published_audit = audit.model_copy(
            update={"input_hashes": input_hashes, "output_hashes": output_hashes}
        )
        write_json_atomic(audit_stage, published_audit.model_dump(mode="json"))
        _publish_files(
            {
                output / "combatants.parquet": parquet_stage,
                output / "combatants.csv": combatants_csv_stage,
                output / "excluded-forms.csv": exclusions_csv_stage,
                audit_path: audit_stage,
            }
        )
        return published_audit
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)


@roster_app.command("build")
def roster_build(
    sources: Annotated[Path, typer.Option("--sources")] = Path("work/sources"),
    output: Annotated[Path, typer.Option("--output")] = Path("outputs"),
    catalog: Annotated[Path, typer.Option("--catalog")] = Path("config/sources.yaml"),
    config: Annotated[Path, typer.Option("--config")] = Path("config/run.toml"),
    decisions: Annotated[Path, typer.Option("--decisions")] = Path(
        "config/roster-decisions.csv"
    ),
    edges: Annotated[Path | None, typer.Option("--edges")] = None,
    raw_forms: Annotated[Path | None, typer.Option("--raw-forms")] = None,
    audit: Annotated[Path, typer.Option("--audit")] = Path(
        "work/roster/roster-audit.json"
    ),
    require_cutoff_counts: Annotated[
        bool, typer.Option("--require-cutoff-counts")
    ] = False,
) -> None:
    """Verify, derive, validate, then atomically publish the final roster."""
    if not require_cutoff_counts:
        _fail("roster build requires --require-cutoff-counts before any final writes")
    raw_path = raw_forms if raw_forms is not None else sources / "raw-forms.json"
    edge_path = edges if edges is not None else sources / "evolution-edges.json"
    ledger_path = sources / "source-ledger.json"
    try:
        run_config = load_run_config(config)
        records, coverage_gaps, verified_source_ids = _verify_sources(
            ledger_path, catalog, run_config.evidence_cutoff
        )
        raw_rows = _load_raw_forms(raw_path)
        decision_rows = load_form_decisions_csv(decisions)
        evolution_edges = _load_evolution_edges(edge_path)
        _check_source_ids(raw_rows, verified_source_ids, "raw forms")
        _check_source_ids(decision_rows, verified_source_ids, "decisions")
        _check_source_ids(evolution_edges, verified_source_ids, "evolution edges")
        built = build_roster(raw_rows, decision_rows, run_config)
        evolved = assign_evolution_metadata(built, evolution_edges)
        canonical = canonicalize_tracks(evolved).model_copy(
            update={
                "exclusions": tuple(
                    sorted(evolved.exclusions, key=lambda row: row.source_form_id)
                )
            }
        )
        validated_audit = validate_roster(canonical, run_config, True).model_copy(
            update={"coverage_gaps": coverage_gaps}
        )
        input_hashes = {
            "catalog": _digest(catalog),
            "config": _digest(config),
            "decisions": _digest(decisions),
            "evolution_edges": _digest(edge_path),
            "raw_forms": _digest(raw_path),
            **{
                f"source_blob:{record.source_id}": _digest(Path(record.blob_path))
                for record in records
                if record.source_id in verified_source_ids
            },
            "source_ledger": _digest(ledger_path),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        _stage_and_publish(canonical, validated_audit, input_hashes, output, audit)
    except Exception as error:  # noqa: BLE001 - stable CLI error boundary
        _fail(error)


if __name__ == "__main__":
    app()
