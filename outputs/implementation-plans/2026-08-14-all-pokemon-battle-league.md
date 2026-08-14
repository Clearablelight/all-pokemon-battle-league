# All-Pokémon Battle League Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the approved exhaustive game-mechanics, lore/animation, evolution-family, consensus, lookup, and portable-report design from frozen sources through verified final artifacts.

**Architecture:** Four independently reviewable plans share versioned Python schemas and immutable source/phase receipts. Foundation runs first; mechanics and lore then run in parallel from the same canonical roster; ranking/report joins only validated canonical outputs and packages one answer-first HTML report.

**Tech Stack:** Python 3.12 data/evidence/ranking pipeline; Node.js 22 and TypeScript mechanics worker; pinned Pokémon Showdown; PyArrow interchange; deterministic source/model/seed hashes; Data Analytics canonical portable report renderer.

## Global Constraints

- The approved design at `docs/superpowers/specs/2026-08-14-all-pokemon-battle-league-design.md` is the controlling product contract.
- Schema version begins at `1.0.0`; changing a field's meaning requires a schema-version change and migration test.
- The evidence cutoff, species assertions, combat rules, track separation, eligibility, pair accounting, thresholds, score bands, and acceptance gates are not adjustable during a run.
- The same frozen `combatants.parquet`, source lock, and ruleset version feed mechanics, lore, consensus, evolution, lookup, and report work.
- Every phase writes a receipt with input hashes, output hashes, counts, versions, thresholds, seed identities, limitations, and completion state.
- A failed required-source, roster, legality, evidence, pair-count, champion-sensitivity, or artifact validation gate stops downstream finalization.
- Network retrieval is confined to the source-lock phase; scoring, simulation, ranking, lookup, and report packaging run offline from verified snapshots.
- Mechanics and lore may execute concurrently only after the foundation receipt passes; ranking/report begins only after both phase receipts pass.
- No ordinary item, trainer, teammate, switching, lethal death-battle rule, universal modifier duplication, fabricated unreleased profile, or forced categorical winner may enter downstream work.
- Final user-facing deliverables are limited to the files named by the design and live under `outputs/`; intermediate work remains under `work/`.

---

## Plan suite and execution order

1. [`2026-08-14-all-pokemon-foundation-roster.md`](2026-08-14-all-pokemon-foundation-roster.md) — environment, source ledger, manifest, exclusions, equivalence, and evolution mapping.
2. Run these two plans concurrently after the foundation gate:
   - [`2026-08-14-all-pokemon-game-mechanics.md`](2026-08-14-all-pokemon-game-mechanics.md) — legal profiles/builds, controller, calibration, exhaustive mechanics pairs, and uncertainty.
   - [`2026-08-14-all-pokemon-lore-adjudication.md`](2026-08-14-all-pokemon-lore-adjudication.md) — evidence, dossiers, arenas, fighting-style adjudication, exhaustive lore pairs, and review.
3. [`2026-08-14-all-pokemon-ranking-report.md`](2026-08-14-all-pokemon-ranking-report.md) — pair audits, four leaderboards, consensus, every family matchup, lookup, run manifest, and portable HTML.

Each worker must read this index, the controlling design, and its assigned plan before editing. A worker may change only files owned by its plan unless the cross-plan interface itself is being reviewed and updated in all consumers in the same commit.

## Cross-plan contracts

| Contract | Owner | Consumers | Required identity |
|---|---|---|---|
| `RunConfig` | Foundation | All phases | `ruleset_version`, `model_version`, cutoff, seed root |
| `SourceRecord` ledger | Foundation | Roster, game, lore, report | source ID plus exact SHA-256 blob |
| `Combatant` | Foundation | Game, lore, ranking, lookup | stable ID plus three canonical IDs |
| `GameProfile` / `BattleBuild` | Mechanics | Mechanics scoring, report audit | profile/build/legality hashes |
| Game pair row | Mechanics | Ranking, consensus, evolution, lookup, report | sorted pair key, W/D/L, score, interval, method |
| `LoreDossier` | Lore | Lore scoring, report audit | continuity/evidence/policy hashes |
| Lore pair row | Lore | Ranking, consensus, evolution, lookup, report | sorted pair key, nine decisions, bounds/status |
| Combined pair row | Ranking/report | Ranking, evolution, lookup, report | both component IDs/methods and exact 50/50 score |
| `FinalRunManifest` | Ranking/report | HTML and final validator | every input/output hash and coverage gap |

Cross-language exchanges use Arrow schema metadata keys `schema_version`, `ruleset_version`, `model_version`, `source_lock_sha256`, and `created_by`. JSON control messages add `request_id` and reject unknown fields. Python alone writes final Parquet so physical encoding and row ordering remain consistent.

## Frozen implementation decisions made explicit by planning

- Showdown is pinned at commit `b22742debfdce6e640193384f5731b9030f9cb6e` and extended through a registered Champions-derived mod; controller snapshots never depend on `onModifySpecies`.
- The normative surrogate partition is 7,000 fit / 1,500 temperature validation / 1,500 untouched conformal, correcting the obsolete `80/20` checklist wording in the first draft.
- Forms distinct in only one track use an exact 0.5 `track_equivalence` component in the identical track when their consensus head-to-head would otherwise be a self-pair.
- Lore factor aggregation uses published weights 0.30 threat/durability, 0.15 initiative, 0.15 control/incapacitation, 0.10 mobility/range, 0.15 stamina/recovery/form duration, 0.10 combat judgment/style, and 0.05 environment fit; champion and top-25 sensitivity to that choice is mandatory.
- Copeland is wins minus losses. Exact primary-score ties remain co-leaders instead of being broken by stable-ID order.

## Resource and persistence gate

Before the 10,000-pair mechanics calibration, run the fixed 32-pair × 64-paired-seed benchmark from the game plan. Save battles/second, turns/second, controller cache hit rate, projected wall time, projected checkpoint/final disk, available disk, and a 20% headroom check. Refuse the full phase if headroom fails. If projected wall time makes the current environment unsuitable, preserve the source/roster/profile/build receipts and supply the exact resumable command rather than weakening sample counts or silently truncating pairs.

Every exhaustive phase shards deterministically, validates `.partial` files before atomic rename, records SHA-256 per shard, and resumes only hash-valid work. Pair processing order must not influence analytical ranks, escalation queues, review queues, seeds, or final rows.

## Spec coverage map

| Design section | Implemented by |
|---|---|
| 1–3 goal, constraints, reporting job | Index plus report Tasks 5–6 |
| 4 contestant manifest and forms | Foundation Tasks 2, 4–6 |
| 5 shared fight rules | Mechanics Tasks 1–4; lore Tasks 3–5 |
| 6 mechanics track | Mechanics Tasks 1–6 |
| 7 lore/animation track | Lore Tasks 1–6 |
| 8 pair accounting and ranking | Ranking/report Tasks 1–2 and 4 |
| 9 evolution-family coverage | Foundation Task 5; ranking/report Task 3 |
| 10 component boundaries | All four plans and cross-plan contracts above |
| 11 deliverables | Ranking/report Tasks 1, 3, 4, and 6 |
| 12 report structure | Ranking/report Tasks 5–6 |
| 13 validation gates | Tests in every task; finalization Task 4; report Task 6 |
| 14 limitations | Phase receipts, run manifest, and report caveats |
| 15 source baseline | Foundation Task 3 and source lock |
| 16 acceptance criteria | Ranking/report Tasks 4 and 6 |
| 17 out of scope | Foundation rules, mechanics format, lore policy, final validator |

## Final clean-room command sequence

After task-level commits and phase receipts pass, run from the repository root:

```bash
.venv/bin/pip install --require-hashes -r requirements.lock
pnpm install --frozen-lockfile
.venv/bin/pokemon-league sources verify --ledger work/sources/source-ledger.json --offline
.venv/bin/pokemon-league roster build --sources work/sources --output outputs --require-cutoff-counts
.venv/bin/pokemon-league game run --config config/run.toml --combatants outputs/combatants.parquet --work work/game --output outputs
.venv/bin/pokemon-league lore run --config config/run.toml --combatants outputs/combatants.parquet --evidence data/lore --work work/lore --output outputs
.venv/bin/pokemon-league finalize --config config/run.toml --work work --output outputs
.venv/bin/pokemon-league report build --outputs outputs --artifact work/report/artifact.json
.venv/bin/pokemon-league report deliver --renderer /Users/landonstrain/.codex/plugins/cache/openai-curated-remote/data-analytics/0.2.8-13ceeea1f599/skills/build-report/scripts/deliver_portable_artifact.mjs --artifact work/report/artifact.json --output outputs/all-pokemon-battle-league-report.html --receipt work/report/delivery-receipt.json
.venv/bin/ruff check src tests
.venv/bin/mypy src tests
pnpm --dir packages/game-core test
.venv/bin/pytest tests -v
.venv/bin/pokemon-league validate --config config/run.toml --outputs outputs
```

Expected completion state: every test passes; phase receipts and `outputs/run-manifest.json` agree on counts/hashes; the portable-renderer receipt is `passed` or explicitly disclosed `structural_only`; all design deliverables exist; the first report section is `Executive Summary`; every leader claim, individual matchup, and evolution-family row traces to saved canonical results.
