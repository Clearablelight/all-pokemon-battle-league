"""Synthetic-only end-to-end contracts for the final roster publication gate."""

from __future__ import annotations

import csv
import hashlib
import json
import stat
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest
from typer.testing import CliRunner

import pokemon_league.cli as league_cli
from pokemon_league.cli import app
from pokemon_league.roster.loader import DECISION_CSV_HEADER
from pokemon_league.schemas.roster import Combatant, ExcludedForm

SYNTHETIC_NOTICE = "Synthetic test-only data. This is not real Pokémon evidence or a production roster."
FETCHED_AT = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_catalog(
    path: Path, *, required_ids: tuple[str, ...] = ("synthetic-roster",)
) -> None:
    rows = []
    for source_id in reversed(required_ids):
        rows.append(
            "  - source_id: "
            f"{source_id}\n"
            f"    url: https://example.test/{source_id}\n"
            "    source_kind: synthetic-test-only\n"
            "    continuity_id: synthetic-fixture\n"
            "    required: true\n"
            f"    license_note: {SYNTHETIC_NOTICE}\n"
            "    commit: allowed-pin-metadata-is-not-a-SourceSpec-field\n"
        )
    path.write_text("sources:\n" + "".join(rows), encoding="utf-8")


def _append_optional_catalog_gap(path: Path) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            "  - source_id: optional-synthetic-context\n"
            "    url: https://example.test/optional-synthetic-context\n"
            "    source_kind: synthetic-test-only\n"
            "    continuity_id: synthetic-fixture\n"
            "    required: false\n"
            f"    license_note: {SYNTHETIC_NOTICE}\n"
        )


def _write_config(path: Path) -> None:
    path.write_text(
        'project_version = "1.0.0"\n'
        'ruleset_version = "2026-08-14.1"\n'
        'model_version = "2026-08-14.1"\n'
        "evidence_cutoff = 2026-08-14\n"
        'timezone = "America/Chicago"\n'
        "numbered_species_count = 1025\n"
        'provisional_species = ["Browt", "Pombon", "Gecqua"]\n'
        "turn_cap = 200\n"
        "seed_root = 20260814\n",
        encoding="utf-8",
    )


def _raw_row(number: int) -> dict[str, object]:
    combatant_id = f"species-{number:04d}"
    return {
        "source_form_id": combatant_id,
        "base_species_id": combatant_id,
        "national_number": number,
        "display_name": f"Synthetic Species {number}",
        "form_name": None,
        "official_form_order": 0,
        "source_version": "synthetic-test-only",
        "source_ids": ["synthetic-roster"],
        "catalog_complete_at_cutoff": True,
    }


def _provisional_raw_row(name: str) -> dict[str, object]:
    return {
        "source_form_id": name.lower(),
        "base_species_id": name.lower(),
        "national_number": None,
        "display_name": name,
        "form_name": None,
        "official_form_order": 0,
        "source_version": "synthetic-test-only",
        "source_ids": ["synthetic-roster"],
        "catalog_complete_at_cutoff": True,
    }


def _decision_row(raw: dict[str, object], *, provisional: bool) -> dict[str, str]:
    source_form_id = str(raw["source_form_id"])
    return {
        "source_form_id": source_form_id,
        "inclusion_status": "included",
        "reason_code": "",
        "reason_text": "",
        "activation_class": "intrinsic",
        "activation_rule": "persistent synthetic test identity",
        "required_form_item": "",
        "required_form_condition": "",
        "core_series_player_legal": "false" if provisional else "true",
        "official_player_controllable": "false" if provisional else "true",
        "historical": "false",
        "boss_only": "false",
        "provisional": "true" if provisional else "false",
        "game_profile_status": "incomplete" if provisional else "complete_turn_based",
        "lore_evidence_status": "insufficient" if provisional else "limited",
        "game_equivalence_hint": source_form_id,
        "lore_equivalence_hint": source_form_id,
        "inclusion_rationale": SYNTHETIC_NOTICE,
        "source_ids": "synthetic-roster",
    }


def _excluded_decision_row(raw: dict[str, object]) -> dict[str, str]:
    row = _decision_row(raw, provisional=False)
    row.update(
        {
            "inclusion_status": "excluded",
            "reason_code": "synthetic_cosmetic",
            "reason_text": SYNTHETIC_NOTICE,
            "inclusion_rationale": "",
        }
    )
    return row


def _write_full_synthetic_inputs(root: Path) -> tuple[Path, Path, Path, Path]:
    raw_path = root / "raw-forms.json"
    decisions_path = root / "roster-decisions.csv"
    edges_path = root / "evolution-edges.json"
    config_path = root / "run.toml"
    raw_rows = [_raw_row(number) for number in range(1, 1026)]
    raw_rows.extend(
        _provisional_raw_row(name) for name in ("Browt", "Pombon", "Gecqua")
    )
    excluded_rows = [
        {
            **_raw_row(1),
            "source_form_id": "zeta-synthetic-cosmetic",
            "display_name": "Zeta Synthetic Cosmetic",
            "form_name": "Zeta Cosmetic",
            "official_form_order": 1,
        },
        {
            **_raw_row(2),
            "source_form_id": "alpha-synthetic-cosmetic",
            "display_name": "Alpha Synthetic Cosmetic",
            "form_name": "Alpha Cosmetic",
            "official_form_order": 1,
        },
    ]
    raw_rows.extend(excluded_rows)
    raw_path.write_text(
        json.dumps(raw_rows, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    with decisions_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=DECISION_CSV_HEADER, lineterminator="\n"
        )
        writer.writeheader()
        for raw in raw_rows:
            if raw in excluded_rows:
                writer.writerow(_excluded_decision_row(raw))
            else:
                writer.writerow(
                    _decision_row(raw, provisional=raw["national_number"] is None)
                )
    edges_path.write_text("[]\n", encoding="utf-8")
    _write_config(config_path)
    return raw_path, decisions_path, edges_path, config_path


def _snapshot_synthetic_sources(
    runner: CliRunner,
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    required_ids: tuple[str, ...] = ("synthetic-roster",),
) -> Path:
    catalog_path = root / "sources.yaml"
    _write_catalog(catalog_path, required_ids=required_ids)
    monkeypatch.setattr(league_cli, "_utc_now", lambda: FETCHED_AT)
    monkeypatch.setattr(
        league_cli,
        "fetch_https_bytes",
        lambda url: f"{SYNTHETIC_NOTICE}\n{url}\n".encode(),
    )
    result = runner.invoke(
        app,
        [
            "sources",
            "snapshot",
            "--catalog",
            str(catalog_path),
            "--output",
            str(root),
            "--cutoff",
            "2026-08-14",
        ],
    )
    assert result.exit_code == 0, result.output
    return catalog_path


@pytest.fixture
def synthetic_source_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, Path, Path, Path, Path]:
    source_dir = tmp_path / "synthetic-frozen-sources"
    source_dir.mkdir()
    runner = CliRunner()
    catalog = _snapshot_synthetic_sources(runner, source_dir, monkeypatch)
    _append_optional_catalog_gap(catalog)
    raw, decisions, edges, config = _write_full_synthetic_inputs(source_dir)
    return source_dir, catalog, raw, decisions, edges, config


def _build_args(
    source_dir: Path,
    catalog: Path,
    raw: Path,
    decisions: Path,
    edges: Path,
    config: Path,
    output: Path,
    audit: Path,
    *,
    require_cutoff: bool = True,
) -> list[str]:
    args = [
        "roster",
        "build",
        "--sources",
        str(source_dir),
        "--output",
        str(output),
        "--catalog",
        str(catalog),
        "--config",
        str(config),
        "--raw-forms",
        str(raw),
        "--decisions",
        str(decisions),
        "--edges",
        str(edges),
        "--audit",
        str(audit),
    ]
    if require_cutoff:
        args.append("--require-cutoff-counts")
    return args


def test_sources_snapshot_and_offline_verify_use_only_mocked_local_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The source commands are deterministic and offline verification never fetches."""
    root = tmp_path / "sources"
    root.mkdir()
    runner = CliRunner()
    catalog = _snapshot_synthetic_sources(
        runner, root, monkeypatch, required_ids=("zulu", "alpha")
    )
    ledger = root / "source-ledger.json"
    records = json.loads(ledger.read_text(encoding="utf-8"))["records"]
    assert [record["source_id"] for record in records] == ["alpha", "zulu"]
    assert all(record["retrieved_at"] == "2026-08-14T12:00:00Z" for record in records)

    monkeypatch.setattr(
        league_cli,
        "fetch_https_bytes",
        lambda _: pytest.fail("offline verify attempted network access"),
    )
    verified = runner.invoke(
        app,
        [
            "sources",
            "verify",
            "--ledger",
            str(ledger),
            "--catalog",
            str(catalog),
            "--offline",
        ],
    )
    assert verified.exit_code == 0, verified.output

    corrupt_blob = Path(records[0]["blob_path"])
    corrupt_blob.chmod(stat.S_IRUSR | stat.S_IWUSR)
    corrupt_blob.write_bytes(b"corrupt")
    first = runner.invoke(
        app,
        [
            "sources",
            "verify",
            "--ledger",
            str(ledger),
            "--catalog",
            str(catalog),
            "--offline",
        ],
    )
    second = runner.invoke(
        app,
        [
            "sources",
            "verify",
            "--ledger",
            str(ledger),
            "--catalog",
            str(catalog),
            "--offline",
        ],
    )
    assert first.exit_code == second.exit_code == 2
    assert first.output == second.output
    assert "sha256 mismatch" in first.output


def test_roster_build_refuses_every_write_without_explicit_final_gate(
    synthetic_source_dir: tuple[Path, Path, Path, Path, Path, Path], tmp_path: Path
) -> None:
    """A partial-mode CLI request cannot create output or audit parents."""
    source_dir, catalog, raw, decisions, edges, config = synthetic_source_dir
    output = tmp_path / "not-created-output"
    audit = tmp_path / "not-created-work" / "roster-audit.json"

    result = CliRunner().invoke(
        app,
        _build_args(
            source_dir,
            catalog,
            raw,
            decisions,
            edges,
            config,
            output,
            audit,
            require_cutoff=False,
        ),
    )

    assert result.exit_code == 2
    assert "--require-cutoff-counts" in result.output
    assert not output.exists()
    assert not audit.parent.exists()


@pytest.mark.parametrize(
    ("filename", "normalized_alias"),
    (
        ("combatants.parquet", False),
        ("combatants.csv", False),
        ("excluded-forms.csv", False),
        ("combatants.parquet", True),
        ("combatants.csv", True),
        ("excluded-forms.csv", True),
    ),
)
def test_roster_build_rejects_audit_output_collision_before_any_mutation(
    synthetic_source_dir: tuple[Path, Path, Path, Path, Path, Path],
    tmp_path: Path,
    filename: str,
    normalized_alias: bool,
) -> None:
    """`--audit` cannot overwrite an output through an exact or normalized alias."""
    source_dir, catalog, raw, decisions, edges, config = synthetic_source_dir
    untouched = tmp_path / "not-created"
    output = untouched / "outputs"
    audit = (
        output / "nested" / ".." / filename
        if normalized_alias
        else output / filename
    )

    result = CliRunner().invoke(
        app,
        _build_args(source_dir, catalog, raw, decisions, edges, config, output, audit),
    )

    assert result.exit_code == 2
    assert "publication targets must resolve distinctly" in result.output
    assert not untouched.exists()


def test_roster_build_leaves_destinations_untouched_on_unverified_source(
    synthetic_source_dir: tuple[Path, Path, Path, Path, Path, Path], tmp_path: Path
) -> None:
    """Required-ledger failure happens before any final destination is created."""
    source_dir, catalog, raw, decisions, edges, config = synthetic_source_dir
    ledger = json.loads((source_dir / "source-ledger.json").read_text(encoding="utf-8"))
    Path(ledger["records"][0]["blob_path"]).unlink()
    output = tmp_path / "untouched-output"
    audit = tmp_path / "untouched-work" / "roster-audit.json"

    result = CliRunner().invoke(
        app,
        _build_args(source_dir, catalog, raw, decisions, edges, config, output, audit),
    )

    assert result.exit_code == 2
    assert "missing required blob" in result.output
    assert not output.exists()
    assert not audit.parent.exists()


def test_roster_build_rejects_unknown_source_ids_before_writing(
    synthetic_source_dir: tuple[Path, Path, Path, Path, Path, Path], tmp_path: Path
) -> None:
    """Unknown provenance in raw, decision, or edge inputs cannot pass the ledger gate."""
    source_dir, catalog, raw, decisions, edges, config = synthetic_source_dir
    raw_payload = json.loads(raw.read_text(encoding="utf-8"))
    raw_payload[0]["source_ids"] = ["unknown-source"]
    raw.write_text(json.dumps(raw_payload), encoding="utf-8")
    output = tmp_path / "unknown-output"
    audit = tmp_path / "unknown-work" / "roster-audit.json"

    result = CliRunner().invoke(
        app,
        _build_args(source_dir, catalog, raw, decisions, edges, config, output, audit),
    )

    assert result.exit_code == 2
    assert (
        "unknown or unverified source IDs in raw forms: unknown-source" in result.output
    )
    assert not output.exists()
    assert not audit.parent.exists()


def test_full_synthetic_cutoff_pipeline_exports_stable_schemas_hashes_and_order(
    synthetic_source_dir: tuple[Path, Path, Path, Path, Path, Path], tmp_path: Path
) -> None:
    """Synthetic 1,025+3 data proves the production-capable pipeline without evidence claims."""
    source_dir, catalog, raw, decisions, edges, config = synthetic_source_dir
    output = tmp_path / "published"
    audit_path = tmp_path / "work" / "roster-audit.json"
    runner = CliRunner()
    arguments = _build_args(
        source_dir, catalog, raw, decisions, edges, config, output, audit_path
    )

    first = runner.invoke(app, arguments)
    assert first.exit_code == 0, first.output
    parquet_path = output / "combatants.parquet"
    csv_path = output / "combatants.csv"
    exclusions_path = output / "excluded-forms.csv"
    first_frame = pd.read_parquet(parquet_path)
    first_csv = csv_path.read_bytes()

    expected_combatant_columns = list(Combatant.model_fields)
    expected_exclusion_columns = list(ExcludedForm.model_fields)
    assert first_frame.columns.tolist() == expected_combatant_columns
    assert pd.read_csv(csv_path).columns.tolist() == expected_combatant_columns
    assert pd.read_csv(exclusions_path).columns.tolist() == expected_exclusion_columns
    assert pd.read_csv(exclusions_path)["source_form_id"].tolist() == [
        "alpha-synthetic-cosmetic",
        "zeta-synthetic-cosmetic",
    ]
    assert first_frame.iloc[0]["combatant_id"] == "species-0001"
    assert first_frame.iloc[-3:]["combatant_id"].tolist() == [
        "browt",
        "gecqua",
        "pombon",
    ]
    assert first_frame.shape[0] == 1028

    arrow_schema = pq.read_schema(parquet_path)
    assert pa.types.is_list(arrow_schema.field("source_ids").type)
    metadata = pq.ParquetFile(parquet_path).metadata
    assert all(
        metadata.row_group(0).column(index).compression == "ZSTD"
        for index in range(metadata.num_columns)
    )
    header, first_data = first_csv.decode("utf-8").splitlines()[:2]
    source_ids_index = next(
        index
        for index, name in enumerate(next(csv.reader([header])))
        if name == "source_ids"
    )
    assert next(csv.reader([first_data]))[source_ids_index] == '["synthetic-roster"]'

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["numbered_species_count"] == 1025
    assert audit["provisional_species"] == ["Browt", "Pombon", "Gecqua"]
    assert audit["combatant_count"] == 1028
    assert audit["coverage_gaps"] == ["optional-synthetic-context"]
    assert audit["input_hashes"] == {
        "catalog": _sha256(catalog),
        "config": _sha256(config),
        "decisions": _sha256(decisions),
        "evolution_edges": _sha256(edges),
        "raw_forms": _sha256(raw),
        "source_blob:synthetic-roster": _sha256(
            Path(
                json.loads((source_dir / "source-ledger.json").read_text())["records"][
                    0
                ]["blob_path"]
            )
        ),
        "source_ledger": _sha256(source_dir / "source-ledger.json"),
    }
    assert audit["output_hashes"] == {
        "combatants.csv": _sha256(csv_path),
        "combatants.parquet": _sha256(parquet_path),
        "excluded-forms.csv": _sha256(exclusions_path),
    }

    second = runner.invoke(app, arguments)
    assert second.exit_code == 0, second.output
    pd.testing.assert_frame_equal(first_frame, pd.read_parquet(parquet_path))
    assert csv_path.read_bytes() == first_csv
    second_audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert second_audit["output_hashes"] == {
        "combatants.csv": _sha256(csv_path),
        "combatants.parquet": _sha256(parquet_path),
        "excluded-forms.csv": _sha256(exclusions_path),
    }


def test_writer_failure_publishes_no_final_files_or_orphan_temps(
    synthetic_source_dir: tuple[Path, Path, Path, Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All files finish staging before any final path becomes visible."""
    source_dir, catalog, raw, decisions, edges, config = synthetic_source_dir
    output = tmp_path / "failed-output"
    audit = tmp_path / "failed-work" / "roster-audit.json"

    def fail_csv(*args: object, **kwargs: object) -> None:
        raise RuntimeError("synthetic CSV writer failure")

    monkeypatch.setattr(pd.DataFrame, "to_csv", fail_csv)
    result = CliRunner().invoke(
        app,
        _build_args(source_dir, catalog, raw, decisions, edges, config, output, audit),
    )

    assert result.exit_code == 2
    assert "synthetic CSV writer failure" in result.output
    assert not output.exists()
    assert not audit.parent.exists()
    assert list(tmp_path.rglob("*.tmp")) == []
