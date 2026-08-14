# All-Pokémon Foundation and Roster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the reproducible project foundation, source ledger, battle-distinct contestant manifest, per-track equivalence maps, evolution families, and audited roster exports.

**Architecture:** A Python package owns typed domain records, immutable source snapshots, deterministic IDs, roster rules, and Parquet/CSV exports. Raw source records and curated edge-form decisions stay separate; every derived row carries source and ruleset provenance.

**Tech Stack:** CPython 3.12; Pydantic 2; pandas; PyArrow; orjson; pytest; Hypothesis; TOML/YAML configuration; SHA-256 content addressing.

## Global Constraints

- Evidence cutoff is `2026-08-14` in `America/Chicago`; a later release requires a new run.
- The base roster asserts exactly 1,025 numbered species from Bulbasaur through Pecharunt and exactly three provisional species: Browt, Pombon, and Gecqua.
- Include every evolutionary stage and every combat-relevant form; retain every reviewed exclusion with a machine-readable reason.
- The only boss-form allowlist entry is Eternamax Eternatus.
- Generic Dynamax, ordinary Terastallization, Z-Moves, encounter buffs, and cosmetic-only forms are not contestants.
- Mechanics eligibility requires `game_profile_status = complete_turn_based`; lore eligibility is decided independently.
- The player-legal leaderboard field is `official_player_controllable`, not `core_series_player_legal`.
- Canonical aliases are selected by National number, official form order, then stable ID; consensus collapses only when both track canonical IDs match.
- All generated records retain source IDs, source hashes, source retrieval dates, ruleset version, and model version.
- Final deliverables go only under `outputs/`; raw data, caches, fixtures, and checkpoints go under `work/`.
- Python dependencies are resolved into a checked-in, hash-pinned `requirements.lock`; no unpinned environment may create final artifacts.

---

## File map

- `pyproject.toml` — package metadata, dependency ranges, CLI, pytest, and type-check configuration.
- `requirements.in` / `requirements-dev.in` / `requirements.lock` — direct requirements and the exact hashed environment.
- `config/run.toml` — cutoff, versions, global seed, and frozen numeric rules.
- `config/sources.yaml` — official/technical source URLs, continuity IDs, and retrieval policy.
- `config/roster-decisions.csv` — explicit include/exclude/equivalence decisions for edge forms.
- `src/pokemon_league/config.py` — validated run configuration.
- `src/pokemon_league/schemas/common.py` — shared enums, provenance, and stable pair key types.
- `src/pokemon_league/schemas/roster.py` — combatant, exclusion, evolution, and roster-build records.
- `src/pokemon_league/io.py` — atomic JSON, CSV, and Parquet writes plus hashing.
- `src/pokemon_league/sources/snapshot.py` — source retrieval, hashing, and frozen ledger creation.
- `src/pokemon_league/roster/builder.py` — inclusion/exclusion rule application.
- `src/pokemon_league/roster/equivalence.py` — per-track canonicalization and consensus identity.
- `src/pokemon_league/roster/evolution.py` — family, branch, and stage assignment.
- `src/pokemon_league/roster/validate.py` — cutoff counts, uniqueness, coverage, and flag audits.
- `src/pokemon_league/cli.py` — `sources snapshot` and `roster build` commands.
- `tests/foundation/` and `tests/roster/` — unit, property, and cutoff integration tests.

### Task 1: Reproducible Python project and frozen run configuration

**Files:**
- Create: `.gitignore`
- Create: `.python-version`
- Create: `pyproject.toml`
- Create: `requirements.in`
- Create: `requirements-dev.in`
- Create: `config/run.toml`
- Create: `src/pokemon_league/__init__.py`
- Create: `src/pokemon_league/config.py`
- Create: `tests/fixtures/run.toml`
- Test: `tests/foundation/test_config.py`

**Interfaces:**
- Consumes: the approved design constants.
- Produces: `RunConfig` and `load_run_config(path: Path) -> RunConfig` for every later task.

- [ ] **Step 1: Write the failing configuration test**

```python
from datetime import date
from pathlib import Path

from pokemon_league.config import load_run_config


def test_run_config_freezes_cutoff_and_numeric_rules() -> None:
    config = load_run_config(Path("tests/fixtures/run.toml"))
    assert config.evidence_cutoff == date(2026, 8, 14)
    assert config.timezone == "America/Chicago"
    assert config.numbered_species_count == 1025
    assert config.provisional_species == ("Browt", "Pombon", "Gecqua")
    assert config.turn_cap == 200
    assert config.seed_root == 20260814
```

- [ ] **Step 2: Run the test and verify the missing package failure**

Run: `python3.12 -m venv .venv && .venv/bin/python -m pip install -U pip pip-tools && .venv/bin/pip install -e . && .venv/bin/pytest tests/foundation/test_config.py -v`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'pokemon_league.config'`.

- [ ] **Step 3: Add the package, dependencies, and exact configuration loader**

Use `requires-python = ">=3.12,<3.13"`; put `pydantic>=2.13,<3`, `pandas>=3,<4`, `pyarrow>=25,<26`, `numpy>=2.4,<3`, `scipy>=1.17,<2`, `scikit-learn>=1.8,<2`, `duckdb>=1.4,<2`, `orjson>=3.11,<4`, `httpx>=0.28,<1`, `lxml>=6,<7`, `PyYAML>=6,<7`, `typer>=0.21,<1`, and `jinja2>=3.1,<4` in `requirements.in`; put `pytest>=9,<10`, `hypothesis>=6,<7`, `mypy>=1.18,<2`, and `ruff>=0.14,<1` in `requirements-dev.in`. Configure the `pokemon-league` console script as `pokemon_league.cli:app`.

```python
from datetime import date
from pathlib import Path
import tomllib

from pydantic import BaseModel, ConfigDict, Field


class RunConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    project_version: str
    ruleset_version: str
    model_version: str
    evidence_cutoff: date
    timezone: str
    numbered_species_count: int = Field(ge=1)
    provisional_species: tuple[str, ...]
    turn_cap: int = Field(ge=1)
    seed_root: int


def load_run_config(path: Path) -> RunConfig:
    with path.open("rb") as handle:
        return RunConfig.model_validate(tomllib.load(handle))
```

Set `config/run.toml` to project version `1.0.0`, ruleset version `2026-08-14.1`, model version `2026-08-14.1`, cutoff `2026-08-14`, timezone `America/Chicago`, numbered count `1025`, provisional list `Browt, Pombon, Gecqua`, turn cap `200`, and seed root `20260814`. Ignore `.venv/`, `node_modules/`, `work/`, Python caches, and generated files under `outputs/` except checked-in design/plan documents.

- [ ] **Step 4: Lock and verify the environment**

Run: `.venv/bin/pip-compile --generate-hashes --output-file requirements.lock requirements.in requirements-dev.in && .venv/bin/pip install --require-hashes -r requirements.lock && .venv/bin/pytest tests/foundation/test_config.py -v`

Expected: one passing test and a `requirements.lock` in which every distribution has an exact version and hash.

- [ ] **Step 5: Commit the foundation**

```bash
git add .gitignore .python-version pyproject.toml requirements.in requirements-dev.in requirements.lock config/run.toml src/pokemon_league/__init__.py src/pokemon_league/config.py tests/fixtures/run.toml tests/foundation/test_config.py
git commit -m "build: freeze battle league environment"
```

### Task 2: Shared schemas, deterministic IDs, and atomic artifact I/O

**Files:**
- Create: `src/pokemon_league/schemas/__init__.py`
- Create: `src/pokemon_league/schemas/common.py`
- Create: `src/pokemon_league/schemas/roster.py`
- Create: `src/pokemon_league/io.py`
- Create: `tests/factories.py`
- Test: `tests/foundation/test_ids_and_io.py`
- Test: `tests/roster/test_schema.py`

**Interfaces:**
- Consumes: `RunConfig`.
- Produces: `stable_id(*parts: str) -> str`, `PairKey.of(left_id: str, right_id: str) -> PairKey`, `write_json_atomic(path: Path, value: object) -> str`, `write_table_atomic(frame: pd.DataFrame, parquet_path: Path, csv_path: Path | None) -> dict[str, str]`, `Combatant`, `ExcludedForm`, and `RosterBuild`.

- [ ] **Step 1: Write failing ID, symmetry, validation, and atomic-write tests**

```python
from pathlib import Path
import json

import pytest

from pokemon_league.io import write_json_atomic
from pokemon_league.schemas.common import PairKey, stable_id
from pokemon_league.schemas.roster import GameProfileStatus
from tests.factories import combatant_factory


def test_pair_key_is_order_independent() -> None:
    assert PairKey.of("venusaur", "bulbasaur") == PairKey.of("bulbasaur", "venusaur")


def test_stable_id_normalizes_display_punctuation() -> None:
    assert stable_id("Mr. Mime", "Galar") == "mr-mime--galar"


def test_incomplete_profile_cannot_be_mechanics_eligible() -> None:
    with pytest.raises(ValueError, match="complete_turn_based"):
        combatant_factory(game_profile_status=GameProfileStatus.INCOMPLETE, mechanics_eligible=True)


def test_atomic_json_returns_content_hash(tmp_path: Path) -> None:
    digest = write_json_atomic(tmp_path / "record.json", {"b": 2, "a": 1})
    assert json.loads((tmp_path / "record.json").read_text()) == {"a": 1, "b": 2}
    assert len(digest) == 64
```

- [ ] **Step 2: Run focused tests and verify import failures**

Run: `.venv/bin/pytest tests/foundation/test_ids_and_io.py tests/roster/test_schema.py -v`

Expected: FAIL because the shared schema and I/O modules do not exist.

- [ ] **Step 3: Implement the exact domain contracts**

Define string enums `ActivationClass`, `GameProfileStatus`, `LoreEvidenceStatus`, `PopulationStatus`, and `InclusionStatus`. `Combatant` must contain every manifest field named in design Section 4, plus `national_number: int | None`, `official_form_order: int`, `historical: bool`, `boss_only: bool`, `source_ids: tuple[str, ...]`, `source_version: str`, and `ruleset_version: str`. Add a model validator requiring mechanics eligibility iff the profile is complete and requiring both player flags false for boss-only rows.

Create a test-only `combatant_factory(**overrides)` whose complete valid baseline is Bulbasaur: National number 1, official form order 0, released/intrinsic, complete turn-based/limited lore, both player flags true, mechanics eligible, no required item/condition, all three canonical IDs `bulbasaur`, family `bulbasaur-family`, stage 1, source ID `showdown-pokedex`, source/rules versions `fixture`, and a nonempty inclusion rationale. Apply overrides before `Combatant.model_validate()` so invalid-state tests exercise production validation.

```python
import hashlib
import re
import unicodedata
from pydantic import BaseModel, ConfigDict


def stable_id(*parts: str) -> str:
    normalized = []
    for part in parts:
        ascii_text = unicodedata.normalize("NFKD", part).encode("ascii", "ignore").decode()
        normalized.append(re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-"))
    return "--".join(normalized)


class PairKey(BaseModel):
    model_config = ConfigDict(frozen=True)
    combatant_a_id: str
    combatant_b_id: str

    @classmethod
    def of(cls, left_id: str, right_id: str) -> "PairKey":
        if left_id == right_id:
            raise ValueError("self-pairs are forbidden")
        left, right = sorted((left_id, right_id))
        return cls(combatant_a_id=left, combatant_b_id=right)

    @property
    def value(self) -> str:
        return f"{self.combatant_a_id}__vs__{self.combatant_b_id}"
```

Implement atomic writes by serializing to a sibling temporary file, calling `flush()` and `os.fsync()`, then `os.replace()`. JSON must sort keys and end with a newline. Parquet uses Zstandard compression and CSV uses UTF-8 with stable column order. Return SHA-256 hashes of final bytes.

- [ ] **Step 4: Run schema and I/O tests**

Run: `.venv/bin/pytest tests/foundation/test_ids_and_io.py tests/roster/test_schema.py -v`

Expected: all tests pass; Hypothesis generates reversed pair orders without changing `PairKey.value`.

- [ ] **Step 5: Commit shared contracts**

```bash
git add src/pokemon_league/schemas src/pokemon_league/io.py tests/factories.py tests/foundation/test_ids_and_io.py tests/roster/test_schema.py
git commit -m "feat: add canonical battle league schemas"
```

### Task 3: Immutable source snapshotter and provenance ledger

**Files:**
- Create: `config/sources.yaml`
- Create: `src/pokemon_league/sources/__init__.py`
- Create: `src/pokemon_league/sources/snapshot.py`
- Create: `src/pokemon_league/sources/validate.py`
- Create: `tests/fixtures/sources/local-source.txt`
- Test: `tests/sources/test_snapshot.py`

**Interfaces:**
- Consumes: `RunConfig`, a source list with `source_id`, `url`, `source_kind`, `continuity_id`, `required`, and `license_note`.
- Produces: `SourceRecord`, `snapshot_sources(specs: Sequence[SourceSpec], root: Path, fetched_at: datetime, fetch: FetchBytes) -> tuple[SourceRecord, ...]`, and `validate_source_ledger(records: Sequence[SourceRecord]) -> None`.

- [ ] **Step 1: Write a failing content-addressing test**

```python
from datetime import datetime, timezone
from pathlib import Path

from pokemon_league.sources.snapshot import SourceSpec, snapshot_sources


def test_snapshot_is_content_addressed_and_repeatable(tmp_path: Path) -> None:
    spec = SourceSpec(source_id="fixture", url="memory://fixture", source_kind="technical", continuity_id="shared", required=True, license_note="test")
    fetch = lambda _: b"Bulbasaur\n"
    first = snapshot_sources((spec,), tmp_path, datetime(2026, 8, 14, tzinfo=timezone.utc), fetch)
    second = snapshot_sources((spec,), tmp_path, datetime(2026, 8, 14, tzinfo=timezone.utc), fetch)
    assert first == second
    assert first[0].sha256 == "398c945e5593870adcad9c81aa3ba801a6c6359ea3a2b57878cceb1ebcc68e40"
    assert (tmp_path / "blobs" / first[0].sha256).read_bytes() == b"Bulbasaur\n"
```

- [ ] **Step 2: Run the snapshot test and verify the missing module failure**

Run: `.venv/bin/pytest tests/sources/test_snapshot.py -v`

Expected: FAIL because `pokemon_league.sources.snapshot` is absent.

- [ ] **Step 3: Implement source records and the frozen source policy**

```python
class SourceRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_id: str
    url: str
    source_kind: str
    continuity_id: str
    retrieved_at: datetime
    sha256: str
    byte_count: int
    blob_path: str
    required: bool
    license_note: str


def snapshot_sources(specs, root, fetched_at, fetch):
    records = []
    (root / "blobs").mkdir(parents=True, exist_ok=True)
    for spec in sorted(specs, key=lambda item: item.source_id):
        payload = fetch(spec.url)
        digest = hashlib.sha256(payload).hexdigest()
        blob = root / "blobs" / digest
        if not blob.exists():
            blob.write_bytes(payload)
        records.append(SourceRecord(source_id=spec.source_id, url=spec.url, source_kind=spec.source_kind, continuity_id=spec.continuity_id, retrieved_at=fetched_at, sha256=digest, byte_count=len(payload), blob_path=str(blob), required=spec.required, license_note=spec.license_note))
    return tuple(records)
```

The production fetcher must allow only HTTPS, set a descriptive user agent, cap a response at 100 MiB, retry `429`/`5xx` three times with bounded backoff, and never overwrite an existing blob. `config/sources.yaml` must contain every baseline URL from design Section 15 plus the pinned Pokémon Showdown Git commit and `@smogon/calc` registry record. `validate_source_ledger` rejects duplicate IDs, missing required blobs, mismatched hashes, cutoff-violating publication dates, and sources without a continuity ID.

- [ ] **Step 4: Verify source tests and an offline ledger recheck**

Run: `.venv/bin/pytest tests/sources/test_snapshot.py -v && .venv/bin/python -m pokemon_league.sources.validate --ledger work/sources/source-ledger.json --offline`

Expected: unit tests pass; the offline command either verifies every existing record or exits `2` with a sorted list of source IDs that have not yet been snapshotted.

- [ ] **Step 5: Commit source provenance support**

```bash
git add config/sources.yaml src/pokemon_league/sources tests/fixtures/sources tests/sources/test_snapshot.py
git commit -m "feat: add immutable source snapshots"
```

### Task 4: Roster rules and explicit form decisions

**Files:**
- Create: `config/roster-decisions.csv`
- Create: `src/pokemon_league/roster/__init__.py`
- Create: `src/pokemon_league/roster/builder.py`
- Create: `tests/fixtures/roster/raw-forms.json`
- Create: `tests/fixtures/roster/decisions.csv`
- Test: `tests/roster/test_builder.py`

**Interfaces:**
- Consumes: pinned raw species/form rows, `FormDecision` rows, `RunConfig`, and source ledger IDs.
- Produces: `build_roster(raw_forms: Sequence[RawForm], decisions: Sequence[FormDecision], config: RunConfig) -> RosterBuild` with included combatants and exclusions.

- [ ] **Step 1: Write failing inclusion and exclusion fixtures**

```python
def test_builder_keeps_battle_forms_and_audits_cosmetics(raw_forms, form_decisions, run_config) -> None:
    result = build_roster(raw_forms, form_decisions, run_config)
    names = {row.display_name for row in result.combatants}
    assert {"Venusaur", "Mega Venusaur", "Gigantamax Venusaur", "Eternamax Eternatus"} <= names
    assert "Venusaur Shiny" not in names
    assert any(row.display_name == "Venusaur Shiny" and row.reason_code == "cosmetic_only" for row in result.exclusions)
    assert next(row for row in result.combatants if row.display_name == "Eternamax Eternatus").boss_only


def test_provisional_species_are_present_but_not_mechanics_eligible(raw_forms, form_decisions, run_config) -> None:
    result = build_roster(raw_forms, form_decisions, run_config)
    for name in ("Browt", "Pombon", "Gecqua"):
        row = next(item for item in result.combatants if item.display_name == name)
        assert row.provisional and not row.mechanics_eligible
```

- [ ] **Step 2: Run builder tests and verify they fail**

Run: `.venv/bin/pytest tests/roster/test_builder.py -v`

Expected: FAIL because no roster builder exists.

- [ ] **Step 3: Implement deterministic form-rule application**

```python
def build_roster(raw_forms, decisions, config):
    decision_by_source_id = {row.source_form_id: row for row in decisions}
    combatants, exclusions = [], []
    for raw in sorted(raw_forms, key=lambda row: (row.national_number or 9999, row.official_form_order, row.source_form_id)):
        decision = decision_by_source_id.get(raw.source_form_id)
        if decision is None:
            raise ValueError(f"unreviewed form: {raw.source_form_id}")
        if decision.inclusion_status == InclusionStatus.EXCLUDED:
            exclusions.append(ExcludedForm.from_raw(raw, decision, config.ruleset_version))
            continue
        combatants.append(Combatant.from_raw(raw, decision, config.ruleset_version))
    reviewed = {row.source_form_id for row in decisions}
    missing_raw = reviewed - {row.source_form_id for row in raw_forms}
    if missing_raw:
        raise ValueError(f"decisions reference absent source forms: {sorted(missing_raw)}")
    return RosterBuild(combatants=tuple(combatants), exclusions=tuple(exclusions))
```

`FormDecision` must explicitly record inclusion status, reason code/text, activation class/rule, required condition/item, both legality flags, historical/boss/provisional flags, game profile status, lore evidence status, equivalence hints, and source IDs. The allowlist validator rejects every boss flag except `eternatus--eternamax`. Unknown source forms fail closed so a source update cannot silently change scope.

- [ ] **Step 4: Run builder and allowlist tests**

Run: `.venv/bin/pytest tests/roster/test_builder.py -v`

Expected: all tests pass, including rejection of an unreviewed source form and a second boss-only form.

- [ ] **Step 5: Commit explicit roster rules**

```bash
git add config/roster-decisions.csv src/pokemon_league/roster tests/fixtures/roster tests/roster/test_builder.py
git commit -m "feat: build audited combatant roster"
```

### Task 5: Evolution mapping and per-track equivalence

**Files:**
- Create: `src/pokemon_league/roster/evolution.py`
- Create: `src/pokemon_league/roster/equivalence.py`
- Test: `tests/roster/test_evolution.py`
- Test: `tests/roster/test_equivalence.py`

**Interfaces:**
- Consumes: `RosterBuild` and pinned evolution-edge records.
- Produces: `assign_evolution_metadata(build: RosterBuild, edges: Sequence[EvolutionEdge]) -> RosterBuild` and `canonicalize_tracks(build: RosterBuild) -> RosterBuild`.

- [ ] **Step 1: Write failing Bulbasaur-family and asymmetric-equivalence tests**

```python
def test_bulbasaur_family_has_three_internal_pairs(bulbasaur_build, evolution_edges) -> None:
    mapped = assign_evolution_metadata(bulbasaur_build, evolution_edges)
    family = [row for row in mapped.combatants if row.evolution_family_id == "bulbasaur-family"]
    assert {(row.display_name, row.evolution_stage) for row in family} == {("Bulbasaur", 1), ("Ivysaur", 2), ("Venusaur", 3)}
    assert len(list(itertools.combinations(family, 2))) == 3


def test_consensus_collapses_only_when_both_track_ids_match(asymmetric_alias_build) -> None:
    result = canonicalize_tracks(asymmetric_alias_build)
    first, second = result.combatants
    assert first.game_canonical_combatant_id == second.game_canonical_combatant_id
    assert first.lore_canonical_combatant_id != second.lore_canonical_combatant_id
    assert first.consensus_canonical_combatant_id != second.consensus_canonical_combatant_id
```

- [ ] **Step 2: Run both tests and verify missing-function failures**

Run: `.venv/bin/pytest tests/roster/test_evolution.py tests/roster/test_equivalence.py -v`

Expected: FAIL because mapping and canonicalization functions are absent.

- [ ] **Step 3: Implement graph mapping and deterministic canonical selection**

```python
def canonical_sort_key(combatant):
    return (combatant.national_number or 9999, combatant.official_form_order, combatant.combatant_id)


def canonicalize_tracks(build):
    game_ids = choose_canonical_ids(build.combatants, "game_equivalence_group", canonical_sort_key)
    lore_ids = choose_canonical_ids(build.combatants, "lore_equivalence_group", canonical_sort_key)
    consensus_groups = {}
    for row in build.combatants:
        consensus_groups.setdefault((game_ids[row.combatant_id], lore_ids[row.combatant_id]), []).append(row)
    consensus_ids = {
        member.combatant_id: min(members, key=canonical_sort_key).combatant_id
        for members in consensus_groups.values()
        for member in members
    }
    rows = []
    for row in build.combatants:
        game_id = game_ids[row.combatant_id]
        lore_id = lore_ids[row.combatant_id]
        consensus_id = consensus_ids[row.combatant_id]
        rows.append(row.model_copy(update={"game_canonical_combatant_id": game_id, "lore_canonical_combatant_id": lore_id, "consensus_canonical_combatant_id": consensus_id}))
    return build.model_copy(update={"combatants": tuple(rows)})
```

Evolution mapping must find weakly connected components, preserve branches, assign stage as longest distance from a root, tag cycles as invalid, and never merge region-specific branches unless an explicit source edge connects them. Equivalence validation compares the modeled-property fingerprint within each track before permitting a shared group; a mismatch raises with the exact differing fields.

- [ ] **Step 4: Run mapping, equivalence, and property tests**

Run: `.venv/bin/pytest tests/roster/test_evolution.py tests/roster/test_equivalence.py -v`

Expected: all tests pass; randomized input order produces byte-identical canonical IDs.

- [ ] **Step 5: Commit evolution and equivalence rules**

```bash
git add src/pokemon_league/roster/evolution.py src/pokemon_league/roster/equivalence.py tests/roster/test_evolution.py tests/roster/test_equivalence.py
git commit -m "feat: map evolution and track aliases"
```

### Task 6: Full roster audit, CLI, and foundation exports

**Files:**
- Create: `src/pokemon_league/roster/validate.py`
- Create: `src/pokemon_league/cli.py`
- Create: `tests/roster/test_validate.py`
- Create: `tests/integration/test_roster_cutoff.py`
- Create: `outputs/.gitkeep`

**Interfaces:**
- Consumes: source ledger, raw form snapshot, decisions, evolution edges, and all earlier roster functions.
- Produces: `validate_roster(build: RosterBuild, config: RunConfig, require_cutoff_counts: bool) -> RosterAudit`, `combatants.parquet`, `combatants.csv`, `excluded-forms.csv`, and `work/roster/roster-audit.json`.

- [ ] **Step 1: Write failing audit and CLI tests**

```python
def test_cutoff_audit_requires_all_species(full_roster_build, run_config) -> None:
    audit = validate_roster(full_roster_build, run_config, require_cutoff_counts=True)
    assert audit.numbered_species_count == 1025
    assert audit.provisional_species == ("Browt", "Pombon", "Gecqua")
    assert audit.duplicate_combatant_ids == ()
    assert audit.unreviewed_source_form_ids == ()
    assert audit.invalid_alias_groups == ()


def test_cli_writes_expected_columns(cli_runner, frozen_source_dir, tmp_path) -> None:
    result = cli_runner.invoke(app, ["roster", "build", "--sources", str(frozen_source_dir), "--output", str(tmp_path), "--require-cutoff-counts"])
    assert result.exit_code == 0
    columns = set(pd.read_parquet(tmp_path / "combatants.parquet").columns)
    assert {"combatant_id", "game_canonical_combatant_id", "lore_canonical_combatant_id", "consensus_canonical_combatant_id"} <= columns
```

- [ ] **Step 2: Run audit tests and verify failure**

Run: `.venv/bin/pytest tests/roster/test_validate.py tests/integration/test_roster_cutoff.py -v`

Expected: FAIL because validation and the CLI are not implemented.

- [ ] **Step 3: Implement fail-closed audits and deterministic exports**

```python
def validate_roster(build, config, require_cutoff_counts):
    numbered = {row.national_number for row in build.combatants if row.national_number is not None}
    provisional = tuple(sorted(row.display_name for row in build.combatants if row.provisional))
    errors = collect_roster_errors(build)
    if require_cutoff_counts and (len(numbered) != config.numbered_species_count or set(provisional) != set(config.provisional_species)):
        errors.append("cutoff species assertion failed")
    if errors:
        raise RosterValidationError("; ".join(sorted(errors)))
    return RosterAudit.from_build(build, numbered, provisional)
```

The CLI pipeline order is snapshot verification, parse, roster decision application, evolution mapping, equivalence canonicalization, validation, then atomic export. Sort combatants by National number/form order/stable ID and exclusions by source form ID. Record every input/output hash in the audit JSON. Refuse final `outputs/` writes unless `--require-cutoff-counts` is present and every required source has a verified blob.

- [ ] **Step 4: Run the complete foundation gate**

Run: `.venv/bin/ruff check src tests && .venv/bin/mypy src && .venv/bin/pytest tests/foundation tests/sources tests/roster tests/integration/test_roster_cutoff.py -v && .venv/bin/pokemon-league sources snapshot --catalog config/sources.yaml --output work/sources --cutoff 2026-08-14 && .venv/bin/pokemon-league sources verify --ledger work/sources/source-ledger.json --offline && .venv/bin/pokemon-league roster build --sources work/sources --output outputs --require-cutoff-counts`

Expected: static checks and tests pass; `outputs/combatants.parquet`, `outputs/combatants.csv`, `outputs/excluded-forms.csv`, and `work/roster/roster-audit.json` exist; the audit reports 1,025 numbered species and the three named provisional species.

- [ ] **Step 5: Commit the tested roster foundation**

```bash
git add src/pokemon_league/roster/validate.py src/pokemon_league/cli.py tests/roster/test_validate.py tests/integration/test_roster_cutoff.py outputs/.gitkeep
git commit -m "feat: validate and export complete roster"
```

## Phase completion gate

Do not begin mechanics or lore adjudication until the full source ledger and roster audit pass from a clean checkout. Save the commit SHA, roster artifact hashes, canonical-universe sizes, excluded-form count, and coverage gaps in `work/phase-receipts/foundation-roster.json`.
