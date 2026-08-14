# All-Pokémon Ranking, Lookup, and Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert canonical game and lore pair records into auditable champions, consensus results, every evolution-family comparison, a local matchup lookup, a final run manifest, and one portable answer-first HTML report.

**Architecture:** Python validates and orients canonical pair tables, computes separate round robins and exact 50/50 consensus, materializes evolution and lookup outputs, and assembles a bounded canonical analytics artifact. The Data Analytics portable renderer validates and packages that same artifact once into the self-contained HTML deliverable.

**Tech Stack:** Python 3.12; pandas; PyArrow; DuckDB; Pydantic; Typer; pytest; Hypothesis; Data Analytics `build-report` canonical artifact contract and portable HTML renderer; native report charts routed through `data-analytics:visualize-data`.

## Global Constraints

- Each full track table has exactly one row per unordered non-self pair in its unique canonical universe, including explicit unavailable rows.
- The available numeric subset for eligible roster size `N` has exactly `N * (N - 1) / 2` rows.
- Primary game score is `P(win) + 0.5 * P(draw)`; primary lore score is the weighted central score; B's oriented score is exactly one minus A's.
- Primary ranking is total expected points; outright wins, categorical record, Copeland, maximin, uncertainty, head-to-head, and Condorcet are secondary evidence.
- Copeland is declared wins minus declared losses; proven draws and unresolved results contribute zero.
- Exact primary-score ties remain co-leaders; stable display order never fabricates a unique champion.
- True Condorcet requires a declared categorical win over every eligible opponent; a declared loss or proven draw makes status `none`, while only unresolved/unavailable blockers produce `possible`.
- Player-legal game ranking uses only `official_player_controllable = true` and mechanics-eligible entrants; unrestricted game ranking includes every mechanics-eligible boss profile.
- Consensus uses only entrants and pairs available in both tracks and averages game and lore scores exactly 50/50.
- When two consensus entrants share one underlying track canonical ID, that track supplies score `0.5` and method `track_equivalence`; no self-pair is created or queried.
- Evolution family output includes every internal unique pair across branches, regional paths, and battle forms; evolutionary stage provides no score bonus.
- The Bulbasaur/Ivysaur/Venusaur regression family has exactly three pair rows.
- Report audience is `product stakeholders`; the title is short, `Executive Summary` is the first visible section after the title, and the answer precedes methodology.
- The report names unrestricted game, player-legal game, lore, and consensus leaders separately and never calls the 50/50 result canonical truth.
- Every visual has adjacent interpretation and canonical source metadata; million-scale pair detail stays in Parquet/compressed CSV.
- HTML is the one selected delivery surface and must be built from validated `artifact.json` through the canonical portable renderer; do not build a second viewer.
- All listed final files resolve inside `outputs/`; intermediate artifact JSON, receipts, chart maps, and caches stay under `work/`.

---

## File map

- `src/pokemon_league/pairs.py` — canonical pair skeletons, orientation, alias/self-equivalence resolution, and audits.
- `src/pokemon_league/ranking/round_robin.py` — expected points, records, Copeland, maximin, and uncertainty.
- `src/pokemon_league/ranking/condorcet.py` — true/possible/none status.
- `src/pokemon_league/ranking/consensus.py` — consensus universe and exact 50/50 pair join.
- `src/pokemon_league/evolution/report.py` — every within-family combination and track lookup.
- `src/pokemon_league/lookup.py` / `outputs/lookup_matchup.py` — exact-name/stable-ID pair query and orientation.
- `src/pokemon_league/pipeline/manifest.py` / `validate.py` — final run metadata, hashes, counts, and acceptance gates.
- `src/pokemon_league/report/datasets.py` / `charts.py` / `artifact.py` — bounded report snapshot and canonical manifest.
- `work/report/artifact.json` / `source-notes.md` / `chart-map.json` — report source and QA records.
- `tests/ranking/`, `tests/evolution/`, `tests/report/`, `tests/acceptance/` — hand-computed, contract, packaging, and full-run tests.

### Task 1: Canonical pair accounting, orientation, aliases, and lookup

**Files:**
- Create: `src/pokemon_league/pairs.py`
- Create: `src/pokemon_league/lookup.py`
- Create: `outputs/lookup_matchup.py`
- Test: `tests/ranking/test_pair_accounting.py`
- Test: `tests/ranking/test_lookup.py`

**Interfaces:**
- Consumes: combatants and game/lore pair Parquet files.
- Produces: `generate_pair_skeleton(ids: Sequence[str]) -> pd.DataFrame`, `validate_pair_table(rows, canonical_ids, eligible_ids, score_columns) -> PairAudit`, and `lookup_matchup(query_a, query_b, combatants, game, lore, combined) -> MatchupLookup`.

- [ ] **Step 1: Write failing pair-count, mirroring, alias, and equivalence tests**

```python
def test_three_ids_have_three_unordered_pairs() -> None:
    rows = generate_pair_skeleton(("bulbasaur", "ivysaur", "venusaur"))
    assert len(rows) == 3
    assert rows.pair_key.nunique() == 3
    assert not (rows.combatant_a_id == rows.combatant_b_id).any()


def test_lookup_mirrors_one_canonical_row(pair_tables, combatants) -> None:
    forward = lookup_matchup("Bulbasaur", "Venusaur", combatants, **pair_tables)
    reverse = lookup_matchup("Venusaur", "Bulbasaur", combatants, **pair_tables)
    assert forward.game.score_for_first + reverse.game.score_for_first == 1
    assert forward.game.pair_key == reverse.game.pair_key


def test_same_underlying_track_is_equivalence_draw(asymmetric_equivalence_fixture) -> None:
    result = lookup_consensus_components(*asymmetric_equivalence_fixture)
    assert result.game.score_a == Decimal("0.5")
    assert result.game.method == "track_equivalence"
    assert result.lore.pair_key is not None
```

- [ ] **Step 2: Run pair tests and verify missing-function failures**

Run: `.venv/bin/pytest tests/ranking/test_pair_accounting.py tests/ranking/test_lookup.py -v`

Expected: FAIL because pair accounting and lookup are absent.

- [ ] **Step 3: Implement sorted keys, audited counts, and bidirectional lookup**

```python
def generate_pair_skeleton(ids):
    ordered = sorted(set(ids))
    return pd.DataFrame(
        {"pair_key": f"{left}__vs__{right}", "combatant_a_id": left, "combatant_b_id": right}
        for left, right in itertools.combinations(ordered, 2)
    )


def orient_score(row, requested_first_id, score_a_column):
    if requested_first_id == row.combatant_a_id:
        return row[score_a_column]
    if requested_first_id == row.combatant_b_id:
        return None if pd.isna(row[score_a_column]) else 1 - row[score_a_column]
    raise ValueError("requested combatant is absent from canonical pair")
```

Validate no self-pair, no mirror duplicate, exact full and available combinatorial counts, score complements, probability totals, null unavailable numerics, and one canonical resolution per alias. Name lookup is case/punctuation insensitive but reports an ambiguity with candidate stable IDs rather than guessing. The output wrapper imports only installed `pokemon_league.lookup`, accepts two positional names/IDs plus `--json`, and defaults its data directory to its own `outputs/` directory.

- [ ] **Step 4: Run pair, alias, and CLI lookup tests**

Run: `.venv/bin/pytest tests/ranking/test_pair_accounting.py tests/ranking/test_lookup.py -v && .venv/bin/python outputs/lookup_matchup.py Bulbasaur Venusaur --json`

Expected: tests pass; the fixture query returns game and lore orientations from one canonical row and an explicit consensus eligibility/method record.

- [ ] **Step 5: Commit pair accounting and lookup**

```bash
git add src/pokemon_league/pairs.py src/pokemon_league/lookup.py outputs/lookup_matchup.py tests/ranking/test_pair_accounting.py tests/ranking/test_lookup.py
git commit -m "feat: audit and query canonical matchups"
```

### Task 2: Track rankings, uncertainty, Condorcet status, and exact consensus

**Files:**
- Create: `src/pokemon_league/ranking/__init__.py`
- Create: `src/pokemon_league/ranking/round_robin.py`
- Create: `src/pokemon_league/ranking/condorcet.py`
- Create: `src/pokemon_league/ranking/consensus.py`
- Test: `tests/ranking/test_round_robin.py`
- Test: `tests/ranking/test_condorcet.py`
- Test: `tests/ranking/test_consensus.py`

**Interfaces:**
- Consumes: validated pair tables and eligible pool definitions.
- Produces: `rank_round_robin(matchups, eligible_ids, leaderboard_id) -> pd.DataFrame`, `condorcet_status(oriented_rows) -> CondorcetAssessment`, and `build_consensus_pairs(combatants, game, lore) -> pd.DataFrame`.

- [ ] **Step 1: Write failing hand-calculated rank, Condorcet, and consensus tests**

```python
def test_expected_points_copeland_and_maximin(hand_computed_league) -> None:
    ranking = rank_round_robin(hand_computed_league.rows, hand_computed_league.ids, "fixture")
    alpha = ranking.set_index("combatant_id").loc["alpha"]
    assert alpha.total_expected_points == Decimal("1.6")
    assert alpha.outright_wins == 2
    assert alpha.copeland_score == 2
    assert alpha.maximin_score == Decimal("0.7")


def test_condorcet_distinguishes_true_possible_and_none() -> None:
    assert condorcet_status(all_wins()).status == "true"
    assert condorcet_status(wins_plus_unresolved()).status == "possible"
    assert condorcet_status(wins_plus_proven_draw()).status == "none"
    assert condorcet_status(one_loss()).status == "none"


def test_consensus_is_exact_half_and_track_equivalence(game_row, lore_row) -> None:
    combined = combine_pair_components(game_row, lore_row)
    assert combined.score_a == (game_row.score_a + lore_row.score_a) / 2
    equivalent = combine_pair_components(track_equivalence_component(), lore_row)
    assert equivalent.score_a == (Decimal("0.5") + lore_row.score_a) / 2
```

- [ ] **Step 2: Run ranking tests and verify failures**

Run: `.venv/bin/pytest tests/ranking/test_round_robin.py tests/ranking/test_condorcet.py tests/ranking/test_consensus.py -v`

Expected: FAIL because ranking and consensus functions do not exist.

- [ ] **Step 3: Implement oriented totals and the intersection consensus universe**

```python
def oriented_rows(matchups, eligible_ids, score_a="score_a"):
    for row in matchups.itertuples(index=False):
        if not row.available:
            continue
        if row.combatant_a_id in eligible_ids and row.combatant_b_id in eligible_ids:
            yield row.combatant_a_id, row.combatant_b_id, Decimal(str(getattr(row, score_a))), row.outcome_status
            yield row.combatant_b_id, row.combatant_a_id, Decimal("1") - Decimal(str(getattr(row, score_a))), mirror_status(row.outcome_status)


def combine_pair_components(game_component, lore_component):
    if not game_component.available or not lore_component.available:
        return CombinedPair.unavailable(game_component, lore_component)
    return CombinedPair.from_scores((game_component.score_a + lore_component.score_a) / Decimal("2"), game_component, lore_component)
```

For each entrant, compute total and normalized expected points, lower/upper totals, categorical points, outright W/D/unresolved/L counts, Copeland wins-minus-losses, maximin, direct tied-group score, and robust/possible rank interval. Dense-rank exact primary ties and mark them co-leaders. Build four pools: official-player-controllable mechanics, unrestricted mechanics, lore eligible, and intersection consensus. Consensus canonical IDs group entrants by the tuple of underlying canonical IDs; identical tuple groups collapse deterministically, one-ID matches use exact 0.5 track equivalence, and distinct IDs use canonical pair lookup. Average component intervals and retain both component method/confidence/source IDs.

- [ ] **Step 4: Run rank and consensus tests**

Run: `.venv/bin/pytest tests/ranking/test_round_robin.py tests/ranking/test_condorcet.py tests/ranking/test_consensus.py -v`

Expected: all hand-computed totals pass; co-leaders remain ties; true/possible/none Condorcet rules pass; consensus score and intervals are exact 50/50; unavailable pairs never enter totals.

- [ ] **Step 5: Commit ranking engines**

```bash
git add src/pokemon_league/ranking tests/ranking/test_round_robin.py tests/ranking/test_condorcet.py tests/ranking/test_consensus.py
git commit -m "feat: rank mechanics lore and consensus leagues"
```

### Task 3: Complete evolution-family matchup output

**Files:**
- Create: `src/pokemon_league/evolution/__init__.py`
- Create: `src/pokemon_league/evolution/report.py`
- Test: `tests/evolution/test_family_report.py`

**Interfaces:**
- Consumes: combatants, all three pair tables, and full-league ranking rows.
- Produces: `build_evolution_matchups(combatants, game, lore, combined, rankings) -> pd.DataFrame` and `outputs/evolution-family-matchups.csv`.

- [ ] **Step 1: Write failing Bulbasaur, branching, alias, and stage-neutral tests**

```python
def test_bulbasaur_family_has_exact_three_rows(bulbasaur_inputs) -> None:
    rows = build_evolution_matchups(**bulbasaur_inputs)
    assert set(zip(rows.combatant_a_name, rows.combatant_b_name)) == {
        ("Bulbasaur", "Ivysaur"),
        ("Bulbasaur", "Venusaur"),
        ("Ivysaur", "Venusaur"),
    }
    assert len(rows) == 3


def test_branch_family_uses_all_combinations(eevee_inputs) -> None:
    rows = build_evolution_matchups(**eevee_inputs)
    member_count = eevee_inputs["combatants"].consensus_canonical_combatant_id.nunique()
    assert len(rows) == member_count * (member_count - 1) // 2
    assert "evolution_stage_bonus" not in rows.columns
```

- [ ] **Step 2: Run evolution report test and verify failure**

Run: `.venv/bin/pytest tests/evolution/test_family_report.py -v`

Expected: FAIL because the family reporter does not exist.

- [ ] **Step 3: Implement all internal combinations and nullable track references**

```python
def family_pairs(combatants):
    for family_id, family in combatants.groupby("evolution_family_id", sort=True):
        members = family.sort_values(["evolution_stage", "national_number", "official_form_order", "combatant_id"])
        for left, right in itertools.combinations(members.itertuples(index=False), 2):
            yield family_id, left, right
```

For each combination, resolve game/lore/consensus canonical pair IDs or an exact same-track equivalence marker, preserve unavailable reasons, store each track's status/central/lower/upper/decisive factors, and attach each entrant's full-league normalized record. Do not score or order by stage. Keep aliases searchable without emitting duplicate canonical family rows.

- [ ] **Step 4: Run every family coverage test and export fixture**

Run: `.venv/bin/pytest tests/evolution/test_family_report.py -v`

Expected: Bulbasaur has three rows; Eevee and regional branches have all combinations; singleton families have zero rows; every emitted pair resolves to saved canonical track records.

- [ ] **Step 5: Commit evolution reporting**

```bash
git add src/pokemon_league/evolution tests/evolution/test_family_report.py
git commit -m "feat: report every evolution family matchup"
```

### Task 4: Combined output files, final run manifest, and end-to-end validation

**Files:**
- Create: `src/pokemon_league/pipeline/__init__.py`
- Create: `src/pokemon_league/pipeline/manifest.py`
- Create: `src/pokemon_league/pipeline/validate.py`
- Create: `src/pokemon_league/pipeline/finalize.py`
- Modify: `src/pokemon_league/cli.py`
- Test: `tests/acceptance/test_pair_coverage.py`
- Test: `tests/acceptance/test_final_outputs.py`

**Interfaces:**
- Consumes: foundation, mechanics, lore, ranking, and evolution receipts.
- Produces: `finalize_league(inputs: FinalizeInputs) -> FinalRunManifest`, `outputs/combined-matchups.parquet`, `outputs/combined-matchups.csv.gz`, `outputs/rankings.csv`, `outputs/evolution-family-matchups.csv`, and `outputs/run-manifest.json`.

- [ ] **Step 1: Write failing output inventory, hash, and count tests**

```python
EXPECTED_SUPPORTING_OUTPUTS = {
    "combatants.parquet", "combatants.csv", "excluded-forms.csv", "game-builds.parquet",
    "game-matchups.parquet", "game-matchups.csv.gz", "lore-dossiers.parquet",
    "lore-matchups.parquet", "lore-matchups.csv.gz", "combined-matchups.parquet",
    "combined-matchups.csv.gz", "rankings.csv", "evolution-family-matchups.csv",
    "run-manifest.json", "lookup_matchup.py",
}


def test_final_manifest_hashes_every_supporting_output(finalized_output_dir) -> None:
    manifest = json.loads((finalized_output_dir / "run-manifest.json").read_text())
    assert EXPECTED_SUPPORTING_OUTPUTS <= set(manifest["outputs"])
    for name, record in manifest["outputs"].items():
        assert sha256_file(finalized_output_dir / name) == record["sha256"]
```

- [ ] **Step 2: Run acceptance tests and verify missing-finalizer failure**

Run: `.venv/bin/pytest tests/acceptance/test_pair_coverage.py tests/acceptance/test_final_outputs.py -v`

Expected: FAIL because combined outputs and final manifest do not exist.

- [ ] **Step 3: Implement atomic finalization and fail-closed acceptance checks**

```python
def expected_pair_count(size: int) -> int:
    return size * (size - 1) // 2


def finalize_league(inputs):
    validate_all_pair_tables(inputs)
    combined = build_consensus_pairs(inputs.combatants, inputs.game, inputs.lore)
    rankings = build_all_rankings(inputs.combatants, inputs.game, inputs.lore, combined)
    evolution = build_evolution_matchups(inputs.combatants, inputs.game, inputs.lore, combined, rankings)
    output_hashes = write_final_tables_atomically(combined, rankings, evolution, inputs.output_dir)
    manifest = FinalRunManifest.from_receipts(inputs, output_hashes)
    write_json_atomic(inputs.output_dir / "run-manifest.json", manifest.model_dump(mode="json"))
    return manifest
```

Validate every Section 13 and Section 16 acceptance item: species/form scope, canonical counts, pair formulas, mirrored probabilities/scores, profile and lore eligibility, calibration split, simulation seeds, review completion, all ranking totals, Condorcet status, evolution combinations, output schemas, input/output hashes, cutoffs, versions, thresholds, seeds, known limitations, and unresolved coverage. Refuse finalization when champion-sensitive simulation/review remains unperformed; allow disclosed residual intervals only after the three-pass cap is recorded.

- [ ] **Step 4: Run full data acceptance and finalization**

Run: `.venv/bin/pytest tests/acceptance/test_pair_coverage.py tests/acceptance/test_final_outputs.py -v && .venv/bin/pokemon-league finalize --config config/run.toml --work work --output outputs`

Expected: all supporting outputs exist, schemas/counts/hashes pass, rankings derive only from canonical saved pairs, and `run-manifest.json` records every limitation and phase receipt.

- [ ] **Step 5: Commit final data assembly**

```bash
git add src/pokemon_league/pipeline src/pokemon_league/cli.py tests/acceptance/test_pair_coverage.py tests/acceptance/test_final_outputs.py
git commit -m "feat: finalize battle league data products"
```

### Task 5: Report datasets, narrative spine, and native visualization contracts

**Files:**
- Create: `src/pokemon_league/report/__init__.py`
- Create: `src/pokemon_league/report/datasets.py`
- Create: `src/pokemon_league/report/charts.py`
- Create: `src/pokemon_league/report/narrative.py`
- Create: `work/report/source-notes.md`
- Create: `work/report/chart-map.json`
- Test: `tests/report/test_datasets.py`
- Test: `tests/report/test_narrative.py`

**Interfaces:**
- Consumes: final rankings, matchups, evolution output, and run manifest.
- Produces: `build_report_snapshot(output_dir: Path) -> ReportSnapshot`, `build_report_blocks(snapshot) -> tuple[dict, ...]`, and bounded datasets `champions`, `top_ranks`, `rank_comparison`, `contender_matrix`, `decisive_fights`, `evolution_summary`, and `coverage`.

- [ ] **Step 1: Invoke the visualization workflow and write failing report-data tests**

Before editing chart code, read and use `data-analytics:visualize-data` to confirm chart family, fields, encodings, accessibility, and final-context QA for each planned visual. Record the approved contracts in `work/report/chart-map.json`.

```python
def test_report_snapshot_is_bounded_and_answer_complete(final_outputs) -> None:
    snapshot = build_report_snapshot(final_outputs)
    assert {"unrestricted_game", "player_legal_game", "lore", "consensus"} == set(snapshot.champions.track)
    assert len(snapshot.top_ranks) <= 60
    assert len(snapshot.rank_comparison) <= 50
    assert len(snapshot.contender_matrix) <= 225
    assert snapshot.coverage.iloc[0].evidence_cutoff == "2026-08-14"


def test_first_visible_section_is_executive_summary(final_outputs) -> None:
    blocks = build_report_blocks(build_report_snapshot(final_outputs))
    markdown = [block["markdown"] for block in blocks if block["type"] == "markdown"]
    assert markdown[0].startswith("# Every Pokémon, Head to Head")
    assert markdown[1].startswith("## Executive Summary")
```

- [ ] **Step 2: Run report-data tests and verify failures**

Run: `.venv/bin/pytest tests/report/test_datasets.py tests/report/test_narrative.py -v`

Expected: FAIL because report datasets and narrative blocks do not exist.

- [ ] **Step 3: Implement the answer-first report spine and bounded chart datasets**

```python
REPORT_SECTIONS = (
    "Executive Summary",
    "The winner depends on the rules",
    "Game strength and lore strength diverge",
    "The fights that decide the crown",
    "Evolution does not guarantee dominance",
    "Look up any matchup",
    "What would change the answer",
    "Further questions",
    "Caveats and assumptions",
)


def champion_sentence(row):
    qualifier = "co-leads" if row.leader_count > 1 else "leads"
    return f"**{row.display_name} {qualifier} the {row.track_label} league** with {row.normalized_expected_points:.1%} expected points across eligible opponents."
```

Create a top-15 horizontal leaderboard by track, a shared top-25 game-vs-lore rank dumbbell/slope view, a top-12 contender matchup matrix, and an evolution-stage distribution only if the chart contract remains readable; otherwise use the exact evolution table and record the omission in source notes. Each visual gets one adjacent interpretation block and source ID. The Executive Summary has two to four short bullets naming all four leader categories, Condorcet status, disagreement, and material uncertainty. Explain eligibility/denominator before body comparisons. Include practical lookup instructions, further questions, and caveats without a redundant visible sources appendix.

- [ ] **Step 4: Run report dataset, narrative, and chart-contract tests**

Run: `.venv/bin/pytest tests/report/test_datasets.py tests/report/test_narrative.py -v`

Expected: tests pass; each major section has one visible heading, every chart has adjacent interpretation and canonical provenance, bounded datasets carry denominators/confidence, and no unavailable entrant is presented as a loser.

- [ ] **Step 5: Commit the report model**

```bash
git add src/pokemon_league/report work/report/source-notes.md work/report/chart-map.json tests/report/test_datasets.py tests/report/test_narrative.py
git commit -m "feat: shape answer first pokemon report"
```

### Task 6: Canonical artifact, portable HTML packaging, and final QA

**Files:**
- Create: `src/pokemon_league/report/artifact.py`
- Create: `src/pokemon_league/report/delivery.py`
- Modify: `src/pokemon_league/cli.py`
- Create: `tests/report/test_artifact.py`
- Create: `tests/acceptance/test_report_delivery.py`
- Generate: `work/report/artifact.json`
- Generate: `work/report/delivery-receipt.json`
- Generate: `outputs/all-pokemon-battle-league-report.html`

**Interfaces:**
- Consumes: `ReportSnapshot`, report blocks, canonical source metadata, output hashes, and the installed canonical renderer path.
- Produces: `build_artifact(output_dir: Path) -> dict[str, object]`, `deliver_artifact(renderer: Path, artifact: Path, html: Path, receipt: Path) -> DeliveryReceipt`, validated `work/report/artifact.json`, and the self-contained HTML report.

- [ ] **Step 1: Write failing artifact-shape and report-delivery tests**

```python
def test_artifact_uses_one_report_surface(final_outputs) -> None:
    artifact = build_artifact(final_outputs)
    assert artifact["surface"] == "report"
    assert artifact["manifest"]["title"] == "Every Pokémon, Head to Head"
    assert artifact["snapshot"]["status"] in {"ready", "partial"}
    assert isinstance(artifact["snapshot"]["datasets"], dict)
    assert artifact["manifest"]["blocks"][0]["markdown"].startswith("# Every Pokémon, Head to Head")
    assert artifact["manifest"]["blocks"][1]["markdown"].startswith("## Executive Summary")


def test_all_visible_sources_and_links_are_safe(artifact) -> None:
    encoded = json.dumps(artifact)
    assert "../" not in encoded
    assert "file://" not in encoded
    assert all(source.get("id") for source in artifact["manifest"]["sources"])


def test_primary_report_and_supporting_files_exist(delivered_output_dir) -> None:
    required = {
        "combatants.parquet", "combatants.csv", "excluded-forms.csv", "game-builds.parquet",
        "game-matchups.parquet", "game-matchups.csv.gz", "lore-dossiers.parquet",
        "lore-matchups.parquet", "lore-matchups.csv.gz", "combined-matchups.parquet",
        "combined-matchups.csv.gz", "rankings.csv", "evolution-family-matchups.csv",
        "run-manifest.json", "lookup_matchup.py",
    }
    assert (delivered_output_dir / "all-pokemon-battle-league-report.html").stat().st_size > 0
    assert required <= {path.name for path in delivered_output_dir.iterdir()}
```

- [ ] **Step 2: Run artifact tests and verify failure**

Run: `.venv/bin/pytest tests/report/test_artifact.py tests/acceptance/test_report_delivery.py -v`

Expected: FAIL because the canonical artifact and packaged report do not exist.

- [ ] **Step 3: Build the complete canonical report artifact**

```python
def build_artifact(output_dir: Path) -> dict[str, object]:
    snapshot = build_report_snapshot(output_dir)
    sources = build_canonical_report_sources(output_dir)
    blocks = build_report_blocks(snapshot)
    return {
        "surface": "report",
        "manifest": {
            "schemaVersion": "1.0.0",
            "title": "Every Pokémon, Head to Head",
            "blocks": blocks,
            "sources": sources,
        },
        "snapshot": {
            "status": "ready" if not snapshot.material_access_issues else "partial",
            "datasets": snapshot.as_dataset_mapping(),
            "access_issues": snapshot.material_access_issues,
        },
        "sources": sources,
    }
```

Use native artifact markdown, metric, chart, and table blocks only. Include actual safe source URLs and output dataset identities; keep machine-local paths in private source notes, not artifact source objects. Every chart/table declares `sourceId`, default sort where applicable, fields/columns, denominators, and a semantic fallback dataset. Preserve system light/dark appearance and the report block order.

`deliver_artifact` runs `node <renderer> --input <artifact> --output <html>` exactly once with `subprocess.run(check=True, capture_output=True, text=True)`, parses the renderer's compact JSON receipt, writes that receipt atomically to `work/report/delivery-receipt.json`, and rejects any verification state except `passed` or `structural_only`. It records `structural_only` as a visible handoff limitation without installing a browser or creating a second verifier.

- [ ] **Step 4: Package once through the canonical renderer and run final acceptance**

Run: `.venv/bin/pokemon-league report build --outputs outputs --artifact work/report/artifact.json`

Run: `.venv/bin/pokemon-league report deliver --renderer /Users/landonstrain/.codex/plugins/cache/openai-curated-remote/data-analytics/0.2.8-13ceeea1f599/skills/build-report/scripts/deliver_portable_artifact.mjs --artifact work/report/artifact.json --output outputs/all-pokemon-battle-league-report.html --receipt work/report/delivery-receipt.json`

Run: `.venv/bin/pytest tests/report tests/acceptance -v && .venv/bin/pokemon-league validate --config config/run.toml --outputs outputs`

Expected: renderer receipt reports `stages.verification: passed`, or `structural_only` with semantic chart tables and an explicit QA limitation; title and first section pass; no external requests or unsafe paths occur; every final output link resolves; every acceptance check in design Sections 13 and 16 passes.

- [ ] **Step 5: Commit report source and final receipt**

```bash
git add src/pokemon_league/report/artifact.py src/pokemon_league/report/delivery.py src/pokemon_league/cli.py tests/report/test_artifact.py tests/acceptance/test_report_delivery.py
git commit -m "feat: deliver portable battle league report"
```

## Project completion gate

Run the complete test suite and a clean-room rebuild from only checked-in code, dependency locks, source lock, curated evidence, and saved seeds. Compare every logical table and deterministic text/JSON/CSV hash; validate Parquet schemas and row content independently of physical metadata. The project is complete only when the HTML directly answers the question, all supporting files exist under `outputs/`, the run manifest proves lineage/counts/coverage, champion-sensitive escalations are complete or cap-limited risk is explicit, and any requested pair or evolution-family fight resolves from saved canonical records.
