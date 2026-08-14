"""Command-line source snapshot, verification, and roster publication pipeline."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from pokemon_league.config import load_run_config
from pokemon_league.io import write_json_atomic
from pokemon_league.roster.builder import build_roster
from pokemon_league.roster.equivalence import canonicalize_tracks
from pokemon_league.roster.evolution import assign_evolution_metadata
from pokemon_league.roster.loader import load_form_decisions_csv
from pokemon_league.roster.publish import (
    preflight_publication_targets,
    publish_roster_bundle,
)
from pokemon_league.roster.validate import validate_roster
from pokemon_league.schemas.roster import EvolutionEdge, RawForm
from pokemon_league.sources.bundle import verify_source_bundle
from pokemon_league.sources.catalog import load_source_catalog
from pokemon_league.sources.snapshot import (
    SourceRecord,
    fetch_https_bytes,
    snapshot_sources,
)
from pokemon_league.sources.validate import validate_source_ledger

app = typer.Typer(help="Build the audited all-Pokémon battle-league roster.")
sources_app = typer.Typer(help="Snapshot and verify immutable source evidence.")
roster_app = typer.Typer(help="Build and publish the validated contestant roster.")
app.add_typer(sources_app, name="sources")
app.add_typer(roster_app, name="roster")


def _utc_now() -> datetime:
    """Return the injectable source retrieval timestamp."""
    return datetime.now(UTC)


def _fail(error: BaseException | str) -> None:
    typer.echo(str(error), err=True)
    raise typer.Exit(code=2)


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
        specs = load_source_catalog(catalog)
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
        verify_source_bundle(
            ledger.parent, ledger, catalog, date.fromisoformat(cutoff)
        )
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
    try:
        preflight_publication_targets(output, audit)
    except Exception as error:  # noqa: BLE001 - stable CLI error boundary
        _fail(error)
    raw_path = raw_forms if raw_forms is not None else sources / "raw-forms.json"
    edge_path = edges if edges is not None else sources / "evolution-edges.json"
    ledger_path = sources / "source-ledger.json"
    try:
        run_config = load_run_config(config)
        source_bundle = verify_source_bundle(
            sources, ledger_path, catalog, run_config.evidence_cutoff
        )
        raw_rows = _load_raw_forms(raw_path)
        decision_rows = load_form_decisions_csv(decisions)
        evolution_edges = _load_evolution_edges(edge_path)
        _check_source_ids(
            raw_rows, set(source_bundle.verified_source_ids), "raw forms"
        )
        _check_source_ids(
            decision_rows, set(source_bundle.verified_source_ids), "decisions"
        )
        _check_source_ids(
            evolution_edges,
            set(source_bundle.verified_source_ids),
            "evolution edges",
        )
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
            update={"coverage_gaps": source_bundle.coverage_gaps}
        )
        input_hashes = {
            "catalog": _digest(catalog),
            "config": _digest(config),
            "decisions": _digest(decisions),
            "evolution_edges": _digest(edge_path),
            "raw_forms": _digest(raw_path),
            **{
                f"source_blob:{record.source_id}": _digest(Path(record.blob_path))
                for record in source_bundle.records
                if record.source_id in source_bundle.verified_source_ids
            },
            "source_ledger": _digest(ledger_path),
        }
        publish_roster_bundle(
            canonical, validated_audit, input_hashes, output, audit
        )
    except Exception as error:  # noqa: BLE001 - stable CLI error boundary
        _fail(error)


if __name__ == "__main__":
    app()
