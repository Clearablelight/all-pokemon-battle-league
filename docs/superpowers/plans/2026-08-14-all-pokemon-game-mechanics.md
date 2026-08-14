# All-Pokémon Game-Mechanics Track Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a reproducible one-on-one mechanics result for every canonical game pair, with legal builds, deterministic analytical scoring, adaptive simulation, uncertainty, and separate unrestricted and player-controllable inputs.

**Architecture:** A pinned Pokémon Showdown checkout plus a registered `allpokemon1v1` mod is prepared into disposable `work/` and driven by a long-lived TypeScript worker. Python owns calibration, surrogate inference, shard orchestration, checkpoint validation, and Parquet output; TypeScript and Python exchange versioned Arrow IPC batches and JSON control messages.

**Tech Stack:** Node.js 22; TypeScript; pnpm; Pokémon Showdown commit `b22742debfdce6e640193384f5731b9030f9cb6e`; `@smogon/calc` 0.11.0; Zod; Apache Arrow JS; GLPK; Vitest; Python 3.12; NumPy; SciPy; scikit-learn; PyArrow; pytest.

## Global Constraints

- Every fight uses the same registered Pokémon Showdown Champions-derived custom mod; no battle mixes engine generations.
- Do not use `onModifySpecies` to create contestant profiles because restored Showdown states must preserve the format.
- Level is 100; all IVs are 31; EVs/Stat Points are zero; nature is neutral; ordinary items, trainers, teams, switching, generic Dynamax/Tera/Z-Moves, and tier bans are absent; otherwise legal sleep, evasion, and one-hit-KO options remain available.
- Form-required items occupy the item slot and retain only their pinned official effects and removal/consumption rules.
- Ogerpon's named Tera aspects and Terapagos Terastal/Stellar are the only named Tera contestant exceptions.
- Gigantamax starts active at Dynamax Level 0, has 1.5× maximum HP, lasts three turns, and reverts with proportional current HP.
- Eternamax Eternatus uses only its exact pinned official encounter profile and a dedicated boss validator.
- Game victory is fainting; simultaneous KO is a draw; unresolved state after turn 200 is a loop draw.
- Initial matrices contain at most 16 validated nondominated builds per side; double-oracle search permits at most 20 iterations and 36 builds per side, stopping at no improvement above 0.02.
- The controller is depth three, has no discount, enumerates at most 4,096 chance paths, otherwise uses exactly 256 counter-hash samples independent of the battle seed.
- Leaf weights are exactly 0.50 HP, 0.20 KO tempo, 0.10 action order, 0.10 status/control, and 0.10 boost/recovery/PP.
- Calibration uses exactly 10,000 pair IDs split 7,000 fit, 1,500 temperature validation, and 1,500 untouched split-conformal calibration; coverage is 90%.
- Simulation stages are 64, 256, 1,024, and finalist-only 4,096 paired seeds; each observation is the mean of two reversed-seat battles.
- Escalation is order-independent, capped at three passes, and uses the exact triggers in design Section 6.3.2.
- Every row preserves source, profile, build, ruleset, controller, model, feature, and seed-schedule hashes.

---

## File map

- `.gitmodules` / `vendor/pokemon-showdown` — read-only upstream gitlink at the pinned commit.
- `package.json`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`, `tsconfig.base.json` — exact Node environment.
- `tools/prepare_showdown.py` — verifies the gitlink, copies it to `work/showdown`, applies the overlay, and builds it.
- `packages/game-core/src/showdown-overlay/` — registered format plus generated mod data.
- `packages/game-core/src/protocol.ts` — branded IDs, request/response types, and schema version.
- `packages/game-core/src/profile.ts` / `builds.ts` / `validator.ts` — exact profiles, candidate generation, dominance, and legality.
- `packages/game-core/src/solver.ts` — deterministic zero-sum equilibrium through GLPK.
- `packages/game-core/src/controller/` — leaf components, chance kernel, depth-three recurrence, and action sampling.
- `packages/game-core/src/simulator/` — Showdown adapter, paired seeds, battle runner, confidence sequence, seat test, and JSONL worker.
- `src/pokemon_league/game/` — Python sampling, features, calibration, surrogate, escalation, checkpoints, and orchestrator.
- `tests/game_ts/` / `tests/game/` / `tests/fixtures/game-mini/` — unit, integration, replay, and six-canonical-entrant acceptance fixtures.

### Task 1: Pin Showdown and register the restorable all-era one-on-one format

**Files:**
- Create: `.gitmodules`
- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `tsconfig.base.json`
- Create: `packages/game-core/package.json`
- Create: `packages/game-core/tsconfig.json`
- Create: `tools/prepare_showdown.py`
- Create: `packages/game-core/src/showdown-overlay/config/formats-entry.ts`
- Create: `packages/game-core/src/showdown-overlay/data/mods/allpokemon1v1/scripts.ts`
- Create: `packages/game-core/src/showdown-overlay/data/mods/allpokemon1v1/rulesets.ts`
- Create: `packages/game-core/src/showdown-overlay/data/mods/allpokemon1v1/pokedex.ts`
- Create: `packages/game-core/src/showdown-overlay/data/mods/allpokemon1v1/learnsets.ts`
- Create: `packages/game-core/src/showdown-overlay/data/mods/allpokemon1v1/abilities.ts`
- Create: `packages/game-core/src/showdown-overlay/data/mods/allpokemon1v1/items.ts`
- Create: `packages/game-core/src/showdown-overlay/data/mods/allpokemon1v1/moves.ts`
- Create: `packages/game-core/src/showdown-overlay/data/mods/allpokemon1v1/conditions.ts`
- Create: `packages/game-core/src/showdown/format.ts`
- Test: `packages/game-core/test/format.test.ts`

**Interfaces:**
- Consumes: the verified game source lock and generated profile tables from the roster phase.
- Produces: `prepare_showdown(vendor: Path, worktree: Path, expected_commit: str) -> str` and registered format ID `gen9allpokemon1v1`.

- [ ] **Step 1: Write failing format-invariant tests**

```typescript
import {describe, expect, test} from 'vitest';
import {loadPreparedFormat} from '../src/showdown/format.js';

describe('gen9allpokemon1v1', () => {
  test('freezes the solo rules', async () => {
    const format = await loadPreparedFormat();
    expect(format.mod).toBe('allpokemon1v1');
    expect(format.teamLength?.validate).toEqual([1, 1]);
    expect(format.maxLevel).toBe(100);
    expect(format.defaultLevel).toBe(100);
    expect(format.ruleset).toContain('All Pokemon 1v1 Rules');
    expect(format.banlist).toEqual(expect.arrayContaining(['Dynamax', 'Terastal', 'Z-Move', 'Switching']));
  });
});
```

- [ ] **Step 2: Run the test and verify the missing prepared-format failure**

Run: `pnpm --dir packages/game-core test -- format.test.ts`

Expected: FAIL because the workspace, overlay, and loader do not exist.

- [ ] **Step 3: Add the pinned gitlink, disposable overlay preparation, and format**

Run: `git submodule add https://github.com/smogon/pokemon-showdown.git vendor/pokemon-showdown && git -C vendor/pokemon-showdown checkout b22742debfdce6e640193384f5731b9030f9cb6e`

`package.json` must require Node `>=22,<23`, use pnpm, and expose `test:game`, `build:game`, and `prepare:showdown`. Pin `@smogon/calc` to `0.11.0`; resolve Zod, Apache Arrow, GLPK, xxHash, TypeScript, tsx, and Vitest into `pnpm-lock.yaml`.

```python
def prepare_showdown(vendor: Path, worktree: Path, expected_commit: str) -> str:
    actual = subprocess.run(["git", "-C", str(vendor), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    if actual != expected_commit:
        raise ValueError(f"Showdown commit {actual} does not match {expected_commit}")
    if worktree.exists():
        shutil.rmtree(worktree)
    shutil.copytree(vendor, worktree, ignore=shutil.ignore_patterns(".git", "node_modules"))
    shutil.copytree(Path("packages/game-core/src/showdown-overlay"), worktree, dirs_exist_ok=True)
    subprocess.run(["node", "build"], cwd=worktree, check=True)
    return actual
```

```typescript
export const Formats: FormatList = [{
  name: '[Gen 9] All Pokemon 1v1',
  mod: 'allpokemon1v1',
  ruleset: ['All Pokemon 1v1 Rules'],
  banlist: ['Dynamax', 'Terastal', 'Z-Move', 'Switching'],
  teamLength: {validate: [1, 1], battle: 1},
  maxLevel: 100,
  defaultLevel: 100,
}];
```

The mod's `scripts.ts` sets `inherit: 'champions'`. Put species/type/stat overrides in generated `pokedex.ts`, legal moves in `learnsets.ts`, and required item/Ability/move/condition rules in their corresponding mod files. The ruleset validates one Pokémon, four moves, no team-dependent action, no ordinary item, and the named transformation exceptions. It installs the 200-turn draw hook without modifying species at runtime.

- [ ] **Step 4: Build the disposable engine and run format fixtures**

Run: `pnpm install --frozen-lockfile && .venv/bin/python tools/prepare_showdown.py --vendor vendor/pokemon-showdown --work work/showdown --commit b22742debfdce6e640193384f5731b9030f9cb6e && pnpm --dir packages/game-core test -- format.test.ts`

Expected: the checkout hash is printed, Showdown builds, and the format tests pass.

- [ ] **Step 5: Commit the pinned engine boundary**

```bash
git add .gitmodules vendor/pokemon-showdown package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json packages/game-core tools/prepare_showdown.py
git commit -m "build: pin all pokemon showdown engine"
```

### Task 2: Versioned profiles, candidate builds, and exact legality

**Files:**
- Create: `packages/game-core/src/protocol.ts`
- Create: `packages/game-core/src/profile.ts`
- Create: `packages/game-core/src/builds.ts`
- Create: `packages/game-core/src/validator.ts`
- Create: `packages/game-core/src/showdown/profile-codegen.ts`
- Create: `packages/game-core/test/profile-and-builds.test.ts`
- Create: `tests/fixtures/game-mini/profiles.json`

**Interfaces:**
- Consumes: mechanics-eligible canonical manifest rows and pinned per-form overrides.
- Produces: `GameProfile`, `BattleBuild`, `generateCandidates(profile: GameProfile, opponent: GameProfile) -> readonly BattleBuild[]`, and `validateBuild(build: BattleBuild, profile: GameProfile) -> ValidationResult`.

- [ ] **Step 1: Write failing profile, cap, dominance, and boss-validator tests**

```typescript
test('candidate generation is legal, nondominated, and capped', async () => {
  const builds = await generateCandidates(fixtures.bulbasaur, fixtures.ivysaur);
  expect(builds.length).toBeGreaterThan(0);
  expect(builds.length).toBeLessThanOrEqual(16);
  expect(new Set(builds.map(build => build.buildId)).size).toBe(builds.length);
  for (const build of builds) expect((await validateBuild(build, fixtures.bulbasaur)).ok).toBe(true);
});

test('Eternamax cannot borrow base Eternatus moves', async () => {
  const altered = {...fixtures.eternamaxBuild, moveIds: ['recover', 'flamethrower', 'sludgebomb', 'dynamaxcannon']};
  expect((await validateBuild(altered, fixtures.eternamax)).reasonCode).toBe('boss_profile_mismatch');
});
```

- [ ] **Step 2: Run tests and verify missing generators**

Run: `pnpm --dir packages/game-core test -- profile-and-builds.test.ts`

Expected: FAIL because profile code generation, candidate generation, and validation are absent.

- [ ] **Step 3: Implement schemas and deterministic candidate generation**

```typescript
export interface GameProfile {
  combatantId: string; canonicalCombatantId: string; speciesId: string;
  baseStats: readonly [number, number, number, number, number, number];
  types: readonly string[]; abilityIds: readonly string[]; moveIds: readonly string[];
  requiredItemId: string | null; activationRule: string; validatorKind: 'ordinary' | 'eternamax';
  officialPlayerControllable: boolean; mechanicsEligible: true; profileHash: string;
}

export interface BattleBuild {
  buildId: string; combatantId: string; speciesId: string; abilityId: string;
  moveIds: readonly [string, string, string, string]; itemId: string | null;
  role: BuildRole; level: 100; nature: 'Hardy'; ivs: readonly [31, 31, 31, 31, 31, 31];
  evs: readonly [0, 0, 0, 0, 0, 0]; legalityHash: string;
}
```

Classify physical, special, mixed, priority/speed-control, setup, status/recovery, anti-setup, fixed-damage/Endeavor, retaliation, trapping/Perish Song, and PP-pressure plans. Select the best applicable build per archetype plus at most four opponent-specific counters. Dominance compares type, category, power, accuracy, priority, target, secondary effect, contact, and strategic exception tags. Validate every four-move combination through Showdown; use equality against the pinned exact Eternamax encounter object for `validatorKind = eternamax`.

Profile code generation applies this fail-closed precedence per form: a complete Pokémon Champions turn-based profile first; otherwise the most recent compatible official turn-based main-series profile by the evidence cutoff. Every mapped legacy move uses the shared engine's behavior. A missing compatible stat, type, Ability behavior, learnset, required-item behavior, or transformation rule changes `game_profile_status` to incomplete and prevents profile emission; Z-A-only/realtime forms never inherit base-form values. Remove actions requiring an ally, bench, switch, or defeated teammate, and mark hazards/phazing ineffective when a one-Pokémon side cannot be affected.

- [ ] **Step 4: Run profile and legality fixtures**

Run: `pnpm --dir packages/game-core test -- profile-and-builds.test.ts`

Expected: tests pass for ordinary legality, move-combination restrictions, required items, at most 16 candidates, and the exact boss profile.

- [ ] **Step 5: Commit profiles and legal builds**

```bash
git add packages/game-core/src/protocol.ts packages/game-core/src/profile.ts packages/game-core/src/builds.ts packages/game-core/src/validator.ts packages/game-core/src/showdown/profile-codegen.ts packages/game-core/test/profile-and-builds.test.ts tests/fixtures/game-mini/profiles.json
git commit -m "feat: generate legal one on one builds"
```

### Task 3: Zero-sum build solver and RNG-blind depth-three controller

**Files:**
- Create: `packages/game-core/src/solver.ts`
- Create: `packages/game-core/src/controller/heuristic.ts`
- Create: `packages/game-core/src/controller/chance-kernel.ts`
- Create: `packages/game-core/src/controller/depth-three.ts`
- Test: `packages/game-core/test/solver.test.ts`
- Test: `packages/game-core/test/controller.test.ts`

**Interfaces:**
- Consumes: restorable battle snapshots and canonical legal actions.
- Produces: `solveZeroSum(matrix: readonly (readonly number[])[], tolerance?: number) -> Equilibrium`, `evaluateLeaf(state: ControllerState) -> number`, `TransitionKernel.outcomes(snapshot, jointAction, depth) -> TransitionSet`, and `DepthThreeController.decide(snapshot, perspective) -> ControllerDecision`.

- [ ] **Step 1: Write failing matrix, heuristic, chance, and determinism tests**

```typescript
test('solves rock paper scissors', () => {
  const eq = solveZeroSum([[0, -1, 1], [1, 0, -1], [-1, 1, 0]]);
  expect(eq.value).toBeCloseTo(0, 9);
  expect(eq.rowMix).toEqual(expect.arrayContaining([expect.closeTo(1 / 3, 8), expect.closeTo(1 / 3, 8), expect.closeTo(1 / 3, 8)]));
  expect(eq.exploitability).toBeLessThanOrEqual(1e-9);
});

test('leaf weights are exact', () => {
  const components = {hp: 0.4, tempo: 0.2, order: 1, control: -0.25, sustain: 0.5};
  expect(weightedLeaf(components)).toBeCloseTo(0.365, 12);
});

test('controller value cannot depend on battle seed', () => {
  const left = controller.decide(fixtureSnapshot, 'p1');
  const right = controller.decide({...fixtureSnapshot, hiddenBattleSeed: 'different'}, 'p1');
  expect(left.actionMix).toEqual(right.actionMix);
});
```

- [ ] **Step 2: Run controller tests and verify failures**

Run: `pnpm --dir packages/game-core test -- solver.test.ts controller.test.ts`

Expected: FAIL because solver, leaf components, and recurrence do not exist.

- [ ] **Step 3: Implement the exact controller recurrence**

```typescript
export function weightedLeaf(c: LeafComponents): number {
  return clamp(0.50 * c.hp + 0.20 * c.tempo + 0.10 * c.order + 0.10 * c.control + 0.10 * c.sustain, -1, 1);
}

export function leafComponents(state: ControllerState, perspective: Side): LeafComponents {
  const opponent = otherSide(perspective);
  const selected = state.lastJointAction;
  const hp = hpFraction(state, perspective) - hpFraction(state, opponent);
  const tempo = clamp((expectedKoTurns(state, opponent, perspective) - expectedKoTurns(state, perspective, opponent)) / 10, -1, 1);
  const order = actionOrder(state, selected) === perspective ? 1 : actionOrder(state, selected) === opponent ? -1 : 0;
  const control = clamp(controlSeverity(state, opponent) - controlSeverity(state, perspective), -1, 1);
  const sustain = clamp((stageValue(state, perspective) - stageValue(state, opponent) + recoverableHpFraction(state, perspective) - recoverableHpFraction(state, opponent) + relevantPpFraction(state, perspective) - relevantPpFraction(state, opponent)) / 3, -1, 1);
  return {hp, tempo, order, control, sustain};
}

function value(snapshot: BattleSnapshot, depth: number, perspective: Side): number {
  const terminal = terminalValue(snapshot, perspective);
  if (terminal !== null) return terminal;
  if (depth === 0) return evaluateLeaf(snapshot, perspective);
  const rows = legalActions(snapshot, perspective);
  const columns = legalActions(snapshot, otherSide(perspective));
  const matrix = rows.map(a => columns.map(b => {
    const transition = kernel.outcomes(snapshot, canonicalJointAction(a, b), depth);
    return transition.outcomes.reduce((sum, outcome) => sum + outcome.probability * value(outcome.nextState, depth - 1, perspective), 0);
  }));
  return solveZeroSum(matrix, 1e-9).value;
}
```

Each component follows design Section 6.3.1 exactly and clamps to `[-1,1]`. Enumerate the complete three-turn chance tree only when its distinct paths are at most 4,096; otherwise create exactly 256 Philox/counter-hash samples keyed by state hash, joint action IDs, depth, and controller version. Only `sampleAction(decision, controllerSeed)` may read a controller seed. Canonically order actions; pure ties become a uniform mixture.

`controlSeverity` assigns incapacity this turn `1.00`, sleep/freeze `0.75`, toxic `0.50`, paralysis/burn/poison `0.25`, and each confusion/trapping/seed/comparable volatile `0.15`, capped at `1.00` per side. `stageValue` is the normalized mean of relevant stat stages, `recoverableHpFraction` is immediately available recovery divided by maximum HP, and `relevantPpFraction` is remaining PP divided by starting PP over moves that can still affect the opponent.

- [ ] **Step 4: Run recurrence, branch-limit, and future-RNG tests**

Run: `pnpm --dir packages/game-core test -- solver.test.ts controller.test.ts`

Expected: all tests pass, including exact-vs-sampled branch selection, terminal overrides, identical decisions from identical visible state, and deterministic tie sampling.

- [ ] **Step 5: Commit the controller**

```bash
git add packages/game-core/src/solver.ts packages/game-core/src/controller packages/game-core/test/solver.test.ts packages/game-core/test/controller.test.ts
git commit -m "feat: add deterministic depth three controller"
```

### Task 4: Restorable battle adapter, paired simulation, and uncertainty tests

**Files:**
- Create: `packages/game-core/src/simulator/adapter.ts`
- Create: `packages/game-core/src/simulator/seeds.ts`
- Create: `packages/game-core/src/simulator/runner.ts`
- Create: `packages/game-core/src/simulator/confidence.ts`
- Create: `packages/game-core/src/simulator/seat-test.ts`
- Create: `packages/game-core/src/simulator/worker.ts`
- Test: `packages/game-core/test/simulator.test.ts`
- Test: `packages/game-core/test/confidence.test.ts`

**Interfaces:**
- Consumes: validated builds, controller decisions, and a paired-seed schedule.
- Produces: `LeagueBattleAdapter`, `derivePairedSeed(runSeed, pairKey, seedIndex) -> PairedSeed`, `runPairedSeed(spec, seed) -> PairedObservation`, `empiricalBernstein95(observations) -> Interval`, and `seatReviewRequired(observations) -> boolean`.

- [ ] **Step 1: Write failing replay, draw, paired-mean, and seat-threshold tests**

```typescript
test('one paired seed runs both seats and reorients B-A', async () => {
  const observation = await runPairedSeed(fixtureBattle, derivePairedSeed(20260814, fixtureBattle.pairKey, 0));
  expect(observation.mean).toBeCloseTo((observation.abScore + observation.baScoreReoriented) / 2, 12);
  expect(observation.mean).toBeGreaterThanOrEqual(0);
  expect(observation.mean).toBeLessThanOrEqual(1);
});

test('turn 200 is a loop draw', async () => {
  const result = await adapter.run(loopFixture, controllers);
  expect(result.scoreA).toBe(0.5);
  expect(result.terminationReason).toBe('turn_cap_draw');
  expect(result.turns).toBe(200);
});

test('seat review requires significance and material size', () => {
  expect(seatReviewRequired(materialAndSignificant256)).toBe(true);
  expect(seatReviewRequired(significantButSmall256)).toBe(false);
  expect(seatReviewRequired(materialButOnly64)).toBe(false);
});
```

- [ ] **Step 2: Run simulation tests and verify failures**

Run: `pnpm --dir packages/game-core test -- simulator.test.ts confidence.test.ts`

Expected: FAIL because the battle adapter and statistical functions are absent.

- [ ] **Step 3: Implement adapter and paired-seed statistics**

```typescript
export interface LeagueBattleAdapter {
  validateBuild(build: BattleBuild, profile: GameProfile): Promise<ValidationResult>;
  create(spec: BattleSpec): BattleHandle;
  snapshot(handle: BattleHandle): BattleSnapshot;
  restore(snapshot: BattleSnapshot): BattleHandle;
  legalActions(handle: BattleHandle, side: Side): readonly LegalAction[];
  step(handle: BattleHandle, jointAction: JointAction, prng: BattlePrng): TurnTransition;
  run(spec: BattleSpec, controllers: ControllerPair): Promise<BattleResult>;
}

export async function runPairedSeed(spec: BattleSpec, seed: PairedSeed): Promise<PairedObservation> {
  const ab = await runOne({...spec, seats: 'AB'}, seed);
  const ba = await runOne({...spec, seats: 'BA'}, seed);
  const baScoreReoriented = 1 - ba.scoreForFirstSeat;
  return {abScore: ab.scoreForFirstSeat, baScoreReoriented, mean: (ab.scoreForFirstSeat + baScoreReoriented) / 2};
}

export function empiricalBernstein95(values: readonly number[]): Interval {
  const n = values.length;
  if (n < 2) return {lower: 0, upper: 1};
  const mean = values.reduce((sum, value) => sum + value, 0) / n;
  const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (n - 1);
  const alphaN = 0.05 * 6 / (Math.PI ** 2 * n ** 2);
  const logTerm = Math.log(3 / alphaN);
  const radius = Math.sqrt(2 * variance * logTerm / n) + 3 * logTerm / n;
  return {lower: Math.max(0, mean - radius), upper: Math.min(1, mean + radius)};
}
```

Use Showdown `State.serializeBattle` and `State.deserializeBattle` for controller branches. Cache `(stateHash, depth, controllerVersion)` within each worker. Derive engine and controller seeds with a counter-based hash of run seed, pair key, both build IDs, seed index, and stream purpose. The confidence sequence consumes only paired means; its `alphaN` schedule sums to 0.05, making the union of the displayed empirical-Bernstein intervals anytime-valid. Start seat review only at 256 pairs; require a two-sided paired permutation p-value below 0.01 and absolute AB-vs-BA expected-score difference above 0.05. JSONL worker messages include schema version and request ID and never spawn one process per battle.

- [ ] **Step 4: Run all engine behavior fixtures**

Run: `pnpm --dir packages/game-core test -- simulator.test.ts confidence.test.ts format.test.ts`

Expected: pass for level-100 stats/damage, required-item interactions, type/Ability bypass, priority/speed ties, fixed damage, simultaneous KO, field conflicts, state reversion, named Tera exceptions, G-Max HP/timer/reversion, no switching/allies, turn cap, replays, confidence sequence, and seat review.

- [ ] **Step 5: Commit deterministic simulations**

```bash
git add packages/game-core/src/simulator packages/game-core/test/simulator.test.ts packages/game-core/test/confidence.test.ts
git commit -m "feat: run paired deterministic battles"
```

### Task 5: Stratified calibration, multinomial surrogate, temperature, and conformal interval

**Files:**
- Create: `src/pokemon_league/game/__init__.py`
- Create: `src/pokemon_league/game/sampling.py`
- Create: `src/pokemon_league/game/features.py`
- Create: `src/pokemon_league/game/surrogate.py`
- Create: `src/pokemon_league/game/calibration.py`
- Create: `tests/game/test_sampling.py`
- Create: `tests/game/test_surrogate.py`

**Interfaces:**
- Consumes: canonical game profiles, build-equilibrium features, and 256-paired-seed W/D/L counts.
- Produces: `select_calibration_pairs(features: pd.DataFrame, n: int, seed: int) -> CalibrationSplit`, `fit_surrogate(fit, validation, conformal) -> FrozenSurrogate`, and `FrozenSurrogate.predict(features) -> pd.DataFrame`.

- [ ] **Step 1: Write failing split, temperature-isolation, and conformal tests**

```python
def test_calibration_split_is_exact_disjoint_and_stratified(pair_features) -> None:
    split = select_calibration_pairs(pair_features, n=10_000, seed=20260814)
    assert (len(split.fit_ids), len(split.temperature_ids), len(split.conformal_ids)) == (7000, 1500, 1500)
    assert not (set(split.fit_ids) & set(split.temperature_ids))
    assert not (set(split.fit_ids) & set(split.conformal_ids))
    assert not (set(split.temperature_ids) & set(split.conformal_ids))
    assert set(pair_features.loc[pair_features.rare_interaction, "pair_key"]) <= set(split.all_ids)


def test_conformal_quantile_uses_untouched_1500_rows(calibration_residuals) -> None:
    interval = fit_split_conformal(calibration_residuals, coverage=0.90)
    assert interval.quantile_rank == 1351
    assert interval.sample_count == 1500
```

- [ ] **Step 2: Run Python game tests and verify failures**

Run: `.venv/bin/pytest tests/game/test_sampling.py tests/game/test_surrogate.py -v`

Expected: FAIL because sampling and model code do not exist.

- [ ] **Step 3: Implement the frozen statistical workflow**

```python
@dataclass(frozen=True)
class CalibrationSplit:
    fit_ids: tuple[str, ...]
    temperature_ids: tuple[str, ...]
    conformal_ids: tuple[str, ...]

    @property
    def all_ids(self) -> tuple[str, ...]:
        return self.fit_ids + self.temperature_ids + self.conformal_ids


def conformal_rank(sample_count: int, coverage: float) -> int:
    return min(sample_count, math.ceil((sample_count + 1) * coverage))
```

Stratify on knockout-turn differential deciles, BST deciles, generations, form classes, type combinations, and every rare tag. Fit multinomial logistic regression on the 7,000 fit IDs using W/D/L frequencies. Fit one positive temperature on only the 1,500 validation IDs. Freeze both, then compute absolute expected-score residuals and the 1-based rank 1,351 quantile on only the 1,500 conformal IDs. Save feature columns, coefficients, temperature, partitions, diagnostics, hashes, and model residual allowance. Permit one mixture-driven refit using the same partitions; never inspect conformal residuals to decide whether to refit.

Before the first fit, score every candidate build pair with the depth-three continuation value from the standardized opening state and convert `[-1,1]` to `[0,1]` using `(value + 1) / 2`. Solve that bootstrap payoff matrix to choose the initial equilibrium mixture, then run exactly 256 paired seeds for each of the 10,000 calibration pairs. After fitting, re-solve every calibration build matrix with surrogate payoffs. If any fit or temperature-validation pair changes equilibrium expected score by more than `0.05`, resimulate those pairs once and perform one final fit/temperature fit. Preserve the original 7,000/1,500/1,500 IDs and do not inspect the conformal partition until the second predictor and temperature are frozen; the second fit is final even when smaller changes remain.

- [ ] **Step 4: Run model, calibration, and serialization tests**

Run: `.venv/bin/pytest tests/game/test_sampling.py tests/game/test_surrogate.py -v`

Expected: tests pass; predicted W/D/L totals equal one within `1e-12`, intervals remain inside `[0,1]`, serialized and reloaded predictions match exactly, and conformal coverage diagnostics are saved.

- [ ] **Step 5: Commit the frozen surrogate**

```bash
git add src/pokemon_league/game tests/game/test_sampling.py tests/game/test_surrogate.py
git commit -m "feat: calibrate mechanics surrogate"
```

### Task 6: Exhaustive analytical shards, escalation, double oracle, and final mechanics output

**Files:**
- Create: `src/pokemon_league/game/hard_rules.py`
- Create: `src/pokemon_league/game/equilibrium.py`
- Create: `src/pokemon_league/game/escalation.py`
- Create: `src/pokemon_league/game/checkpoints.py`
- Create: `src/pokemon_league/game/benchmark.py`
- Create: `src/pokemon_league/game/orchestrator.py`
- Create: `src/pokemon_league/game/output.py`
- Modify: `src/pokemon_league/cli.py`
- Create: `tests/game/test_escalation.py`
- Create: `tests/game/test_game_output.py`
- Create: `tests/integration/test_game_mini_league.py`

**Interfaces:**
- Consumes: roster/profile/build artifacts, frozen surrogate, and the TypeScript worker.
- Produces: `score_game_league(inputs: GameRunInputs) -> GameRunReceipt`, `outputs/game-builds.parquet`, `outputs/game-matchups.parquet`, `outputs/game-matchups.csv.gz`, and `work/game/game-run-receipt.json`.

- [ ] **Step 1: Write failing hard-rule, escalation, checkpoint, and mini-league tests**

```python
def test_escalation_reasons_are_order_independent(analytical_rows, analytical_ranking) -> None:
    forward = select_escalations(analytical_rows, analytical_ranking, pass_number=1)
    reverse = select_escalations(analytical_rows.iloc[::-1], analytical_ranking, pass_number=1)
    assert forward == reverse
    assert {"interval_crosses_half", "score_40_to_60", "build_reversal", "intra_evolution"} <= {reason for item in forward for reason in item.reasons}


def test_six_canonical_mini_league_counts(game_mini_run) -> None:
    rows = pd.read_parquet(game_mini_run / "game-matchups.parquet")
    assert len(rows) == 15
    assert rows.available.sum() == 10
    assert rows.pair_key.nunique() == 15
    assert not (rows.combatant_a_id == rows.combatant_b_id).any()
```

- [ ] **Step 2: Run mechanics integration tests and verify failures**

Run: `.venv/bin/pytest tests/game/test_escalation.py tests/game/test_game_output.py tests/integration/test_game_mini_league.py -v`

Expected: FAIL because the exhaustive orchestrator is absent.

- [ ] **Step 3: Implement deterministic sharding and the three-pass escalation loop**

```python
def shard_for_pair(pair_key: str, shard_count: int = 128) -> int:
    digest = hashlib.blake2b(pair_key.encode(), digest_size=8, person=b"pkmn-pair").digest()
    return int.from_bytes(digest, "big") % shard_count


def score_game_league(inputs: GameRunInputs) -> GameRunReceipt:
    benchmark = benchmark_game_engine(inputs, pair_count=32, paired_seed_count=64)
    require_resource_headroom(benchmark, minimum_fraction=Decimal("0.20"))
    analytical = score_all_analytical_shards(inputs)
    ranking = rank_expected_points(analytical)
    current = analytical
    for pass_number in range(1, 4):
        queue = select_escalations(current, ranking, pass_number)
        if not queue:
            break
        replacements = simulate_queue(queue, stages=(64, 256, 1024, 4096), inputs=inputs)
        current = replace_pairs(current, replacements)
        next_ranking = rank_expected_points(current)
        if rankings_stable(ranking, next_ranking, current):
            ranking = next_ranking
            break
        ranking = next_ranking
    return write_game_outputs(current, inputs, ranking)
```

Apply hard immunities, impossible targeting, mandatory form changes, guaranteed KO, and proven loops before the surrogate. Analytical features include KO turns, survival margin, speed/priority, accuracy/critical exposure, recovery, setup/stat reset, status, fixed damage, retaliation, immunity/bypass, form duration, PP pressure, and loop risk. Re-solve simultaneous build matrices after prediction. Invoke double oracle only for finalist, champion, and build-reversal pairs, adding at most one best response per side each iteration.

Escalate every interval crossing `0.5`, central score from `0.40` through `0.60`, viable build-winner reversal, uncovered rare interaction, interval capable of moving either entrant into/out of the frozen analytical top 5%, intra-evolution pair, finalist, upset, and deterministic audit sample. Pass 1 freezes the full analytical leaderboard; Pass 2 freezes every trigger from it; Pass 3 includes only residual champion/top-25 sensitivity. Stop early only when champion and top-25 membership are unchanged and no unreviewed interval can reverse either; disclose residual risk after the third pass.

Checkpoint 128 full-roster shards and 100 calibration shards through `.partial` files, schema/count/input-hash validation, atomic rename, and SHA-256 manifests; resume only checksum-valid shards. Use at most `max(1, availableParallelism() - 1)` long-lived workers. Before calibration, benchmark exactly 32 deterministic pairs at 64 paired seeds, save battles/second, turns/second, controller cache hit rate, projected wall time/disk, available disk, and require 20% disk headroom. A pass freezes its queue before processing any pair.

Assign mechanics confidence A to an exact hard-rule result or a 4,096-paired-seed result with interval half-width at most `0.02`; B to at least 1,024 paired seeds and half-width at most `0.05`; C to at least 256 paired seeds and half-width at most `0.10`; D to analytical-only, 64-paired-seed, or cap-limited wider results. Persist the grade rule, sample count, interval, and categorical unresolved state rather than upgrading confidence from rank importance.

- [ ] **Step 4: Run the complete mechanics acceptance gate**

Run: `pnpm --dir packages/game-core test && .venv/bin/pytest tests/game tests/integration/test_game_mini_league.py -v && .venv/bin/pokemon-league game benchmark --config config/run.toml --combatants outputs/combatants.parquet --work work/game && .venv/bin/pokemon-league game run --config config/run.toml --combatants outputs/combatants.parquet --work work/game --output outputs`

Expected: unit and mini-league tests pass; full run writes all three mechanics deliverables; every canonical-universe pair appears once, every numeric row has W/D/L summing to one, unresolved intervals remain categorical unresolved, aliases add no row, and a rerun resumes verified shards without changing output hashes.

- [ ] **Step 5: Commit the complete mechanics track**

```bash
git add src/pokemon_league/game src/pokemon_league/cli.py tests/game tests/integration/test_game_mini_league.py
git commit -m "feat: score exhaustive mechanics league"
```

## Phase completion gate

Do not rank champions until `work/game/game-run-receipt.json` records pinned source/profile/build/controller/model/seed hashes, exact canonical and available pair counts, calibration partitions, conformal diagnostics, escalation counts by reason and pass, double-oracle stop reasons, seat discrepancies, residual champion/top-25 risk, and final artifact hashes.
