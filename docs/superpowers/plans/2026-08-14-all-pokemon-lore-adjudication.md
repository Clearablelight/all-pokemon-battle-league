# All-Pokémon Lore and Animation Track Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build source-resolved combat dossiers and deterministic lore matchup records for every canonical lore pair, preserving continuity, fighting style, environment, uncertainty, and the 60-second incapacitation rule.

**Architecture:** Curated normalized evidence feeds typed, immutable dossiers; a rule engine resolves move access, continuity, hard interactions, arenas, and weighted factor votes before mapping each of nine scenarios to the approved score bands. Free-form text may summarize saved factors but may never create a result or numeric score.

**Tech Stack:** Python 3.12; Pydantic 2 at input boundaries; frozen dataclasses internally; HTTPX and lxml for source snapshots/parsing; PyArrow and DuckDB for batched results; Typer; pytest; Hypothesis.

## Global Constraints

- The standard entrant is a healthy prime adult with ordinary temperament, intelligence, self-control, fear, and fighting style; named trained specimens are upper-bound evidence unless the continuity proves uniqueness.
- The primary lore lane is `core_game_species`: core-game/Pokédex central traits plus only compatible species-typical tactics corroborated by at least two ordinary animation depictions.
- Every evidence record identifies exact work, continuity, locator, source kind, publication date, directness, subject scope, and strength from 1 through 6, where 1 is repeated direct species-typical evidence and 6 is a lone myth/gag/promotional claim.
- Incompatible continuities are never merged; alternate continuity outcomes are sensitivities, not primary-rank inputs.
- TCG artwork/mechanics are nonliteral unless independent narrative evidence demonstrates the same capability.
- One opponent-independent primary loadout and any validated alternate four-move loadouts are tested simultaneously; no sequential counterpick or unsupported base-form inheritance is allowed.
- Deliberate named attacks, projectiles, status techniques, and offensive feats occupy move slots; only passive anatomy, locomotion, senses, continuous Ability effects, and ordinary biological functions remain innate.
- Lore victory requires 60 continuous seconds without meaningful resistance, return, or recovery; uncertain duration remains unresolved.
- Every eligible dossier needs supported identity/type, offense, durability/vulnerability, locomotion, reaction/behavior, form/Ability, habitat, and at least two independent official evidence records including one direct combat-relevant record.
- Unknown values remain null; travel speed is not reaction speed; camera perspective is not measurement; type is a strong prior rather than an automatic general outcome.
- Confidence grades A through D and conservative/central/generous evidence handling follow design Sections 7.2 and 7.3 exactly.
- Each pair has neutral, A-home, and B-home arenas weighted 0.50/0.25/0.25, each evaluated under conservative, central, and generous evidence for exactly nine decisions when available.
- Arena taxonomy, 10 km neutral diameter, 5 km boundary radius, 2 km altitude/depth, starting-distance formula, 25 m cover offset, and jointly survivable pocket are frozen.
- Field-dependent sustaining conditions occur only in that entrant's home scenario; host conditions win in host arenas and ordinary neutral weather wins in neutral.
- Primary factor weights are `0.30/0.15/0.15/0.10/0.15/0.10/0.05` for threat/durability, initiative, control/incapacitation, mobility/range, stamina/recovery/form duration, combat judgment/style, and environment fit; this transparent implementation choice receives rank-sensitivity analysis.
- `proven_draw`, `unresolved`, and `unavailable` remain distinct; unavailable rows have no numeric score and never rank.
- Every nontrivial claim and every result factor must resolve to saved evidence IDs or an explicitly labeled bounded inference.

---

## File map

- `data/continuities.toml` — exact continuity identities and the primary lane.
- `data/lore/evidence.ndjson` — normalized trait, feat, statement, anti-feat, and inference records.
- `data/lore/move-evidence.ndjson` — exact-form move support and loadouts.
- `data/lore/arena-assignments.csv` — one fixed home arena and provenance per lore entrant.
- `data/lore/review-decisions.ndjson` — immutable human-review overlays that cite evidence and scenario changes.
- `config/lore-scoring.toml` — arena, factor, band, duration, eligibility, and review policy.
- `src/pokemon_league/schemas/lore.py` — typed evidence, dossier, arena, decision, and pair records.
- `src/pokemon_league/lore/evidence.py` / `continuity.py` — source resolution and primary/sensitivity lanes.
- `src/pokemon_league/lore/moves.py` / `dossier.py` / `eligibility.py` — exact move profiles and dossier gate.
- `src/pokemon_league/lore/arena.py` / `incapacitation.py` / `immunity.py` — hard physical and victory rules.
- `src/pokemon_league/lore/factors.py` / `adjudicator.py` / `scoring.py` — deterministic scenario result.
- `src/pokemon_league/lore/pairs.py` / `review.py` / `orchestrator.py` — complete pairs, review overlays, batching, and outputs.
- `tests/lore/` / `tests/fixtures/lore/` / `tests/integration/test_lore_mini_league.py` — unit, provenance, and end-to-end gates.

### Task 1: Typed lore records and exact scoring policy

**Files:**
- Create: `config/lore-scoring.toml`
- Create: `data/continuities.toml`
- Create: `src/pokemon_league/schemas/lore.py`
- Test: `tests/lore/test_domain.py`
- Test: `tests/lore/test_policy.py`

**Interfaces:**
- Consumes: canonical lore manifest IDs and design Section 7.
- Produces: `EvidenceRecord`, `BandedValue`, `LoreMoveProfile`, `LoreDossier`, `ArenaScenario`, `FactorVote`, `ScenarioDecision`, `LorePairResult`, and `load_lore_policy(path: Path) -> LorePolicy`.

- [ ] **Step 1: Write failing domain and policy-invariant tests**

```python
from decimal import Decimal
import pytest

from pokemon_league.schemas.lore import EvidenceRecord, LorePairResult, OutcomeStatus
from pokemon_league.lore.policy import load_lore_policy


def test_evidence_strength_is_one_through_six(valid_evidence_dict) -> None:
    with pytest.raises(ValueError):
        EvidenceRecord.model_validate(valid_evidence_dict | {"evidence_strength": 0})
    with pytest.raises(ValueError):
        EvidenceRecord.model_validate(valid_evidence_dict | {"evidence_strength": 7})


def test_available_pair_requires_nine_decisions(valid_pair_dict) -> None:
    with pytest.raises(ValueError, match="nine"):
        LorePairResult.model_validate(valid_pair_dict | {"decisions": valid_pair_dict["decisions"][:8]})


def test_factor_and_arena_weights_are_exact() -> None:
    policy = load_lore_policy(Path("config/lore-scoring.toml"))
    assert sum(policy.factor_weights.values()) == Decimal("1.00")
    assert policy.arena_weights == {"neutral": Decimal("0.50"), "a_home": Decimal("0.25"), "b_home": Decimal("0.25")}
```

- [ ] **Step 2: Run domain tests and verify missing records**

Run: `.venv/bin/pytest tests/lore/test_domain.py tests/lore/test_policy.py -v`

Expected: FAIL because lore schemas and policy loader do not exist.

- [ ] **Step 3: Implement immutable records and frozen numeric policy**

```python
class OutcomeStatus(StrEnum):
    WIN_A = "win_A"
    WIN_B = "win_B"
    PROVEN_DRAW = "proven_draw"
    UNRESOLVED = "unresolved"
    UNAVAILABLE = "unavailable"


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    evidence_id: str
    combatant_id: str
    trait_name: str
    normalized_value: int | float | bool | str | None
    unit: str | None
    source_id: str
    source_work_id: str
    continuity_id: str
    source_kind: str
    subject_scope: str
    evidence_strength: int = Field(ge=1, le=6)
    is_direct: bool
    is_serious: bool
    is_anti_feat: bool
    is_exceptional_specimen: bool
    is_myth_gag_or_promotional: bool
    is_inference: bool
    contradicted_by: tuple[str, ...]
    locator: str
```

Use `Decimal` for every score/weight. Store factor weights exactly as threat/durability `0.30`, initiative `0.15`, control/incapacitation `0.15`, mobility/range `0.10`, stamina/recovery/form duration `0.15`, combat judgment/style `0.10`, environment fit `0.05`. Map absolute weighted margin below `0.10` to unresolved, `0.10` to under `0.25` to slight, `0.25` to under `0.50` to clear, and `0.50` or more to decisive; hard-rule outcomes bypass factor magnitude. Validate nine available decisions, complementary A/B scores, ordered intervals, null numerics for unavailable rows, and sorted unordered pair IDs.

- [ ] **Step 4: Run typed-record and policy tests**

Run: `.venv/bin/pytest tests/lore/test_domain.py tests/lore/test_policy.py -v`

Expected: tests pass for invalid strengths, score complements, decision counts, interval ordering, and exact Decimal weight sums.

- [ ] **Step 5: Commit lore contracts**

```bash
git add config/lore-scoring.toml data/continuities.toml src/pokemon_league/schemas/lore.py tests/lore/test_domain.py tests/lore/test_policy.py
git commit -m "feat: define lore evidence and score contracts"
```

### Task 2: Source-resolved evidence loading, continuity lanes, and evidence bands

**Files:**
- Create: `data/lore/evidence.ndjson`
- Create: `src/pokemon_league/lore/evidence.py`
- Create: `src/pokemon_league/lore/continuity.py`
- Create: `src/pokemon_league/lore/bands.py`
- Test: `tests/lore/test_evidence.py`
- Test: `tests/lore/test_continuity.py`
- Test: `tests/lore/test_bands.py`

**Interfaces:**
- Consumes: source ledger, combatants, continuity catalog, and evidence NDJSON.
- Produces: `load_evidence(path, source_ledger, combatant_ids) -> tuple[EvidenceRecord, ...]`, `build_continuity_lanes(records) -> ContinuityBundle`, and `aggregate_trait(records) -> BandedValue[object]`.

- [ ] **Step 1: Write failing provenance, continuity, anti-feat, and TCG tests**

```python
def test_every_evidence_record_resolves_source_and_subject(evidence_path, source_ledger, combatant_ids) -> None:
    records = load_evidence(evidence_path, source_ledger, combatant_ids)
    assert records
    assert len({row.evidence_id for row in records}) == len(records)
    assert all(row.source_id in source_ledger.by_id for row in records)
    assert all(row.combatant_id in combatant_ids for row in records)


def test_primary_lane_needs_two_ordinary_animation_depictions(compatible_animation_records) -> None:
    one = build_continuity_lanes(compatible_animation_records[:1])
    two = build_continuity_lanes(compatible_animation_records[:2])
    assert "opening_tactic" not in one.primary_traits
    assert "opening_tactic" in two.primary_traits


def test_gag_and_promotional_claims_do_not_raise_central(records_with_gag) -> None:
    without = aggregate_trait(records_with_gag[:-1])
    with_gag = aggregate_trait(records_with_gag)
    assert with_gag.central == without.central
    assert with_gag.generous != without.generous
```

- [ ] **Step 2: Run evidence tests and verify missing loaders**

Run: `.venv/bin/pytest tests/lore/test_evidence.py tests/lore/test_continuity.py tests/lore/test_bands.py -v`

Expected: FAIL because loaders and aggregation are absent.

- [ ] **Step 3: Implement strict evidence resolution and lane construction**

```python
def load_evidence(path, source_ledger, combatant_ids):
    records = []
    seen = set()
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        record = EvidenceRecord.model_validate_json(line)
        if record.evidence_id in seen:
            raise ValueError(f"duplicate evidence_id {record.evidence_id} on line {line_number}")
        if record.source_id not in source_ledger.by_id:
            raise ValueError(f"unknown source_id {record.source_id}")
        if record.combatant_id not in combatant_ids:
            raise ValueError(f"unknown combatant_id {record.combatant_id}")
        seen.add(record.evidence_id)
        records.append(record)
    return tuple(records)
```

Aggregate only within a continuity and in ascending evidence-strength order: 1 repeated direct species-typical feat, 2 direct ordinary wild feat, 3 official move/Ability/anatomy/behavior/form description, 4 multiple consistent Pokédex statements, 5 exceptional trained/empowered specimen upper bound, and 6 lone statement/myth/gag/promotional claim. Repeated serious ordinary-specimen feats control central; repeated anti-feats lower conservative; exceptional trained specimens and compatible mythic claims can affect generous only. Retcons supersede only through an explicit `supersedes_evidence_id`. TCG physical-combat claims require a second non-TCG narrative evidence ID. The `core_game_species` primary lane admits an animation tactic only after two independent ordinary depictions from distinct work/episode identities and rejects any material conflict into a named sensitivity lane.

- [ ] **Step 4: Run provenance and continuity tests**

Run: `.venv/bin/pytest tests/lore/test_evidence.py tests/lore/test_continuity.py tests/lore/test_bands.py -v`

Expected: tests pass; incompatible work IDs stay separate; all input order permutations produce identical bands and lane hashes.

- [ ] **Step 5: Commit evidence normalization**

```bash
git add data/lore/evidence.ndjson src/pokemon_league/lore/evidence.py src/pokemon_league/lore/continuity.py src/pokemon_league/lore/bands.py tests/lore/test_evidence.py tests/lore/test_continuity.py tests/lore/test_bands.py
git commit -m "feat: normalize continuity aware lore evidence"
```

### Task 3: Exact-form lore moves, combat dossiers, eligibility, and confidence

**Files:**
- Create: `data/lore/move-evidence.ndjson`
- Create: `data/lore/arena-assignments.csv`
- Create: `src/pokemon_league/lore/moves.py`
- Create: `src/pokemon_league/lore/dossier.py`
- Create: `src/pokemon_league/lore/eligibility.py`
- Test: `tests/lore/test_moves.py`
- Test: `tests/lore/test_dossier.py`
- Test: `tests/lore/test_eligibility.py`

**Interfaces:**
- Consumes: exact-form manifest status, form validator, normalized evidence, and home-arena assignments.
- Produces: `resolve_lore_moves(combatant, evidence, validator) -> LoreMoveProfile`, `build_dossier(combatant, lane, move_profile, arena) -> LoreDossier`, and `evaluate_lore_eligibility(dossier) -> LoreEvidenceStatus`.

- [ ] **Step 1: Write failing move-policy, missing-field, and grade tests**

```python
def test_realtime_form_cannot_inherit_base_moves(realtime_form, base_form_move_evidence, validator) -> None:
    profile = resolve_lore_moves(realtime_form, base_form_move_evidence, validator)
    assert profile.primary_moves == ()
    assert profile.profile_status == "insufficient_exact_form_evidence"


@pytest.mark.parametrize("missing_area", ["identity_type", "offense", "durability_vulnerability", "locomotion", "reaction_behavior", "form_ability", "habitat"])
def test_each_required_area_can_fail_eligibility(eligible_dossier, missing_area) -> None:
    altered = eligible_dossier.without_area(missing_area)
    assert evaluate_lore_eligibility(altered) == LoreEvidenceStatus.INSUFFICIENT


def test_deliberate_attack_cannot_be_a_fifth_innate_power(five_attack_profile) -> None:
    with pytest.raises(ValueError, match="move slot"):
        validate_move_and_capability_budget(five_attack_profile)
```

- [ ] **Step 2: Run dossier tests and verify failures**

Run: `.venv/bin/pytest tests/lore/test_moves.py tests/lore/test_dossier.py tests/lore/test_eligibility.py -v`

Expected: FAIL because move resolution and dossier gating are absent.

- [ ] **Step 3: Implement the independent lore move resolver and gate**

```python
def resolve_lore_moves(combatant, evidence, validator):
    exact = [row for row in evidence if row.combatant_id == combatant.combatant_id]
    if combatant.game_profile_status == GameProfileStatus.COMPLETE_TURN_BASED:
        supported = validator.accepted_lore_moves(combatant.combatant_id, exact)
    elif combatant.game_profile_status == GameProfileStatus.REALTIME_ONLY:
        supported = {row.move_id for row in exact if row.source_kind in {"official_realtime", "animation_direct"}}
    else:
        supported = {row.move_id for row in exact if row.source_kind == "animation_direct" and row.subject_scope == "ordinary_specimen"}
    return build_opponent_independent_loadouts(combatant.combatant_id, supported, exact)
```

Build banded dossier fields for every item in design Section 7.3. Keep movement modes and reaction/combat/travel speed distinct. Grade A/B/C/D using the exact source-count/conflict definitions; store the reason and evidence IDs. Eligibility requires all seven evidence areas and two independent official records, one direct and combat-relevant. A limited dossier may rank if it passes; an insufficient dossier produces only unavailable rows. Save population status per continuity and form duration defaults of one exchange/60 seconds/full encounter only when direct duration evidence is absent.

- [ ] **Step 4: Run exact-form, dossier, and eligibility tests**

Run: `.venv/bin/pytest tests/lore/test_moves.py tests/lore/test_dossier.py tests/lore/test_eligibility.py -v`

Expected: tests pass for all profile statuses, alternate simultaneous loadouts, unknown preservation, confidence grades, uniqueness per continuity, provisional insufficiency, and the seven-field gate.

- [ ] **Step 5: Commit dossiers and eligibility**

```bash
git add data/lore/move-evidence.ndjson data/lore/arena-assignments.csv src/pokemon_league/lore/moves.py src/pokemon_league/lore/dossier.py src/pokemon_league/lore/eligibility.py tests/lore/test_moves.py tests/lore/test_dossier.py tests/lore/test_eligibility.py
git commit -m "feat: build eligible lore combat dossiers"
```

### Task 4: Arenas, 60-second incapacitation, immunity, and form duration

**Files:**
- Create: `src/pokemon_league/lore/arena.py`
- Create: `src/pokemon_league/lore/incapacitation.py`
- Create: `src/pokemon_league/lore/immunity.py`
- Test: `tests/lore/test_arena.py`
- Test: `tests/lore/test_incapacitation.py`
- Test: `tests/lore/test_immunity.py`

**Interfaces:**
- Consumes: two eligible dossiers and a scenario role.
- Produces: `build_arena_scenarios(a, b) -> tuple[ArenaScenario, ArenaScenario, ArenaScenario]`, `evaluate_incapacitation(attempt, window_seconds=Decimal('60')) -> IncapacitationVerdict`, and `resolve_attack_route(attack, defender, context) -> RouteResolution`.

- [ ] **Step 1: Write failing geometry, duration, return, and immunity-precedence tests**

```python
@pytest.mark.parametrize(("larger_m", "expected_m"), [(3, 50), (20, 200), (200, 1000)])
def test_starting_separation_formula(larger_m, expected_m) -> None:
    assert starting_separation_m(larger_m) == Decimal(expected_m)


def test_exact_incapacitation_window() -> None:
    assert not evaluate_incapacitation(attempt(duration_seconds=59)).is_victory
    assert evaluate_incapacitation(attempt(duration_seconds=60)).is_victory
    assert not evaluate_incapacitation(attempt(duration_seconds=60, recovery_seconds=59)).is_victory
    assert evaluate_incapacitation(attempt(battlefield_removed=True, return_seconds=61)).is_victory


def test_explicit_bypass_precedes_type_immunity(type_immune_defender, bypass_attack, context) -> None:
    route = resolve_attack_route(bypass_attack, type_immune_defender, context)
    assert route.status == "effective"
    assert route.reason_codes == ("explicit_bypass",)
```

- [ ] **Step 2: Run physical-rule tests and verify failures**

Run: `.venv/bin/pytest tests/lore/test_arena.py tests/lore/test_incapacitation.py tests/lore/test_immunity.py -v`

Expected: FAIL because arena, victory, and route resolvers are absent.

- [ ] **Step 3: Implement fixed geometry and hard-interaction precedence**

```python
def starting_separation_m(larger_height_or_length_m: Decimal) -> Decimal:
    return min(Decimal("1000"), max(Decimal("50"), Decimal("10") * larger_height_or_length_m))


def build_arena_scenarios(a, b):
    separation = starting_separation_m(max(a.height_or_length_m, b.height_or_length_m))
    return (
        neutral_arena(a, b, separation),
        home_arena(host=a, visitor=b, role="a_home", separation=separation),
        home_arena(host=b, visitor=a, role="b_home", separation=separation),
    )
```

Use the frozen 12-arena taxonomy. Start with line of sight where ordinary senses allow it and cover at least 25 m away. Create a connected neutral pocket only when the visitor otherwise dies or is immobilized immediately. Apply host weather in host scenarios and ordinary weather in neutral. Hard route precedence is explicit bypass, exact demonstrated mechanism, core-game type immunity prior, anatomical intangibility, repeated continuity-specific exception, independently evidenced indirect hazard, then uncertain. Incapacitation covers unconsciousness, petrification, sealing, mind control, surrender, sleep/status, restraint, fear, illusions, regeneration, flight, and battlefield return exactly as design Section 7.1.1 specifies.

- [ ] **Step 4: Run arena and interaction fixtures**

Run: `.venv/bin/pytest tests/lore/test_arena.py tests/lore/test_incapacitation.py tests/lore/test_immunity.py -v`

Expected: tests pass for clamps, boundary, pockets, home weather, conflicting field forms, 59/60/61-second cases, regeneration, surrender, sealing, mind effects, uncertainty, type/bypass/Ability/anatomy/hazard precedence, and continuity-specific exceptions.

- [ ] **Step 5: Commit lore fight rules**

```bash
git add src/pokemon_league/lore/arena.py src/pokemon_league/lore/incapacitation.py src/pokemon_league/lore/immunity.py tests/lore/test_arena.py tests/lore/test_incapacitation.py tests/lore/test_immunity.py
git commit -m "feat: enforce lore arena and victory rules"
```

### Task 5: Nine-scenario adjudication and approved score bands

**Files:**
- Create: `src/pokemon_league/lore/factors.py`
- Create: `src/pokemon_league/lore/adjudicator.py`
- Create: `src/pokemon_league/lore/scoring.py`
- Test: `tests/lore/test_factors.py`
- Test: `tests/lore/test_adjudicator.py`
- Test: `tests/lore/test_scoring.py`

**Interfaces:**
- Consumes: two dossiers, three arenas, three evidence cases, simultaneous loadout matrices, and hard-route outcomes.
- Produces: `adjudicate_pair(a, b, policy) -> LorePairResult` and `aggregate_lore_score(decisions, policy) -> WeightedLoreScore`.

- [ ] **Step 1: Write failing hard-result, nine-decision, band, and complement tests**

```python
def test_weighted_score_and_complement() -> None:
    score = aggregate_three_arenas(Decimal("0.875"), Decimal("0.725"), Decimal("0.600"))
    assert score == Decimal("0.76875")
    assert Decimal("1") - score == Decimal("0.23125")


def test_available_pair_has_nine_decisions(eligible_pair, lore_policy) -> None:
    result = adjudicate_pair(*eligible_pair, lore_policy)
    assert len(result.decisions) == 9
    assert {(row.arena_role, row.evidence_case) for row in result.decisions} == {(arena, case) for arena in ("neutral", "a_home", "b_home") for case in ("conservative", "central", "generous")}


def test_mutual_inability_is_proven_draw(mutual_inability_pair, lore_policy) -> None:
    result = adjudicate_pair(*mutual_inability_pair, lore_policy)
    assert result.outcome_status == OutcomeStatus.PROVEN_DRAW
    assert result.central_score_a == Decimal("0.5")
```

- [ ] **Step 2: Run adjudication tests and verify failures**

Run: `.venv/bin/pytest tests/lore/test_factors.py tests/lore/test_adjudicator.py tests/lore/test_scoring.py -v`

Expected: FAIL because factor voting and score mapping are absent.

- [ ] **Step 3: Implement simultaneous factor matrices and score mapping**

```python
def aggregate_three_arenas(neutral: Decimal, a_home: Decimal, b_home: Decimal) -> Decimal:
    return Decimal("0.50") * neutral + Decimal("0.25") * a_home + Decimal("0.25") * b_home


def categorical_status(score_a: Decimal, affirmative_draw: bool) -> OutcomeStatus:
    if affirmative_draw:
        return OutcomeStatus.PROVEN_DRAW
    if score_a > Decimal("0.55"):
        return OutcomeStatus.WIN_A
    if score_a < Decimal("0.45"):
        return OutcomeStatus.WIN_B
    return OutcomeStatus.UNRESOLVED
```

Resolve hard one-way threat, mutual inability, inability to target, habitat viability, form expiry, phasing, regeneration, mind effects, and battlefield removal first. Otherwise score each simultaneous primary/alternate loadout matrix using factor votes from `-2` through `2`, solve the zero-sum loadout matrix, and map its margin to the frozen strength bands. Save exact approved intervals/central values: A decisive `0.80–0.95/0.875`, clear `0.65–<0.80/0.725`, slight `0.55–<0.65/0.600`, unresolved/draw `0.45–<0.55/0.500`, and mirrored B bands `0.400/0.275/0.125`. Weight lower, central, and upper separately; B is exactly one minus A. Mark environment/continuity dependence whenever scenario/lane categorical direction reverses.

Pair confidence is the worst of both dossier grades and the interaction-rule grade after direct review. Store the exact grade contributors. Run sensitivity scenarios for equal `1/7` factor weights and for each baseline factor at `0.8×` and `1.2×`, redistributing the difference proportionally across the other six weights so every scenario sums to one; recompute champion and top-25 membership and save every reversal.

- [ ] **Step 4: Run all nine-scenario and sensitivity tests**

Run: `.venv/bin/pytest tests/lore/test_factors.py tests/lore/test_adjudicator.py tests/lore/test_scoring.py -v`

Expected: tests pass for hard precedence, simultaneous loadouts, exact bands, score complements, proven draw vs unresolved, environment reversal, continuity reversal, evidence bounds, and confidence propagation.

- [ ] **Step 5: Commit deterministic lore adjudication**

```bash
git add src/pokemon_league/lore/factors.py src/pokemon_league/lore/adjudicator.py src/pokemon_league/lore/scoring.py tests/lore/test_factors.py tests/lore/test_adjudicator.py tests/lore/test_scoring.py
git commit -m "feat: adjudicate nine scenario lore fights"
```

### Task 6: Complete canonical pairs, review overlays, and lore exports

**Files:**
- Create: `data/lore/review-decisions.ndjson`
- Create: `src/pokemon_league/lore/pairs.py`
- Create: `src/pokemon_league/lore/review.py`
- Create: `src/pokemon_league/lore/orchestrator.py`
- Modify: `src/pokemon_league/cli.py`
- Test: `tests/lore/test_pairs.py`
- Test: `tests/lore/test_review.py`
- Test: `tests/integration/test_lore_mini_league.py`

**Interfaces:**
- Consumes: canonical lore universe, dossiers, adjudicator, prior analytical ranks, and evidence-citing review overlays.
- Produces: `score_lore_league(inputs: LoreRunInputs) -> LoreRunReceipt`, `outputs/lore-dossiers.parquet`, `outputs/lore-matchups.parquet`, `outputs/lore-matchups.csv.gz`, `work/lore/review-queue.parquet`, and `work/lore/lore-run-receipt.json`.

- [ ] **Step 1: Write failing pair-accounting, unavailable, review, and memory-bound tests**

```python
def test_three_canonical_entries_produce_three_pairs(three_dossiers) -> None:
    rows = list(generate_lore_pairs(three_dossiers))
    assert len(rows) == 3
    assert len({row.pair_key for row in rows}) == 3


def test_insufficient_pair_is_unavailable(eligible_dossier, insufficient_dossier, lore_policy) -> None:
    result = adjudicate_pair(eligible_dossier, insufficient_dossier, lore_policy)
    assert result.outcome_status == OutcomeStatus.UNAVAILABLE
    assert result.central_score_a is None


def test_review_overlay_changes_scenarios_not_direct_score(reviewable_result, review_decision, lore_policy) -> None:
    reviewed = apply_review_decisions(reviewable_result, (review_decision,))
    assert reviewed.central_score_a == aggregate_lore_score(reviewed.decisions, lore_policy).central
    assert review_decision.evidence_ids
```

- [ ] **Step 2: Run pair/review integration tests and verify failures**

Run: `.venv/bin/pytest tests/lore/test_pairs.py tests/lore/test_review.py tests/integration/test_lore_mini_league.py -v`

Expected: FAIL because batching, queues, and orchestration are absent.

- [ ] **Step 3: Implement deterministic batches and immutable evidence review**

```python
def review_reasons(result, ranking_context):
    reasons = set()
    if result.lower_score_a is not None and result.lower_score_a <= Decimal("0.5") <= result.upper_score_a:
        reasons.add("interval_crosses_half")
    if result.confidence == ConfidenceGrade.D:
        reasons.add("confidence_D")
    if result.environment_dependent:
        reasons.add("environment_reversal")
    if result.continuity_dependent:
        reasons.add("continuity_reversal")
    reasons.update(ranking_context.reasons_for(result.pair_key))
    return tuple(sorted(reasons))
```

Generate unordered pairs from canonical IDs only and retain unavailable rows. Stream batches of at most 50,000 rows to `.partial` Parquet, validate schema/count/input hashes, then atomically rename. Queue close, top-ranked, counterintuitive, D-confidence, continuity-dependent, environment-dependent, alternate-loadout-reversal, and champion-sensitive pairs; sort priority descending then pair key. Review overlays may replace scenario bands, reasons, and evidence IDs but never a final score; rerun scoring from reviewed decisions. Preserve all nine decisions, decisive factors, source IDs, assumptions, alternate continuity outcomes, and method label.

- [ ] **Step 4: Run the complete lore acceptance gate**

Run: `.venv/bin/pytest tests/lore tests/integration/test_lore_mini_league.py -v && .venv/bin/pokemon-league lore run --config config/run.toml --combatants outputs/combatants.parquet --evidence data/lore --work work/lore --output outputs`

Expected: every manifest entrant has a dossier; every canonical-universe pair appears once; every eligible pair has nine decisions and complementary scores; insufficient entrants have null unavailable rows and never rank; all claims resolve to source IDs/locators; review overlays reproduce byte-identical decisions; all lore deliverables and receipt hashes exist.

- [ ] **Step 5: Commit the complete lore track**

```bash
git add data/lore/review-decisions.ndjson src/pokemon_league/lore/pairs.py src/pokemon_league/lore/review.py src/pokemon_league/lore/orchestrator.py src/pokemon_league/cli.py tests/lore/test_pairs.py tests/lore/test_review.py tests/integration/test_lore_mini_league.py
git commit -m "feat: score exhaustive lore league"
```

## Phase completion gate

Do not combine tracks until `work/lore/lore-run-receipt.json` records source/evidence/dossier/policy hashes, eligible and insufficient counts, exact canonical and available pair counts, confidence distribution, review triggers and resolution state, alternate-continuity and environment reversals, factor-weight sensitivity, unresolved champion/top-25 risk, and final artifact hashes.
