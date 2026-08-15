# All-Pokémon Production Roster Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task with a fresh implementer, cumulative review package, independent reviewer, and fix loop for every task.

**Goal:** Replace the synthetic-only Foundation gate with a semantically verified source bundle, an exact cutoff roster candidate universe, explicit form/evolution identities, one reviewed decision per candidate, technical profile/equivalence proofs, deterministic production exports, and a clean-room Foundation receipt.

**Architecture:** The existing Python foundation remains the publication boundary. Phase-aware source records freeze a pinned Pokémon Showdown archive plus accessible official context. A sandboxed, deterministic extractor converts those frozen bytes into candidates and form-specific evolution relations. Reviewed rules materialize decisions; transformations share biological evolution nodes while persistent branches retain form nodes. Production publication requires source, extraction, decision, evolution, profile, and equivalence proofs linked by hashes.

**Tech Stack:** Python 3.12, Pydantic, PyArrow, pandas, `truststore==0.10.4`, Node.js 22 for isolated TypeScript data extraction, pinned Pokémon Showdown commit `b22742debfdce6e640193384f5731b9030f9cb6e`, pytest/Hypothesis, Ruff, and mypy.

## Frozen constraints

- The evidence cutoff remains August 14, 2026 even though this completion plan was authored on August 15. Newer releases require a new run.
- Production National identities are exactly numbers 1–1025, Bulbasaur through Pecharunt, plus only the unnumbered provisionals Browt, Pombon, and Gecqua.
- The pinned Showdown commit has tree `70888cfaabd357264d5e1d42a546e5797c04c150` and timestamp `2026-08-14T13:05:31Z`.
- Showdown is a labeled technical implementation source, not first-party canon. Official sources corroborate identities and special forms where retrievable; inaccessible official pages remain explicit gaps.
- Never accept an HTTP status code as evidence without semantic validation. Never disable TLS, hostname checking, or certificate verification.
- Do not commit official HTML, images, upstream archives, or source blobs. Commit derived factual metadata, hashes, decisions, source links, attribution, and the unofficial-project disclaimer only.
- Production candidates default to distinct track identities. A multi-member equivalence group requires a saved full-track proof.
- No mechanics or lore matchup scoring may begin until Task 5 writes a passing production Foundation receipt from a clean checkout.

## Independently observed cutoff cross-checks

These are acceptance cross-checks, not values to manufacture. The extractor must derive and audit them from the frozen archive:

- 1,380 positive-number raw `pokedex.ts` rows: 1,025 base rows plus 355 raw alternate rows.
- 89 generated `cosmeticFormes` identities.
- 3 official provisional identities absent from Showdown.
- Candidate decision universe: 1,472 identities.
- Recommended classification after exact review: 1,375 included combatants and 97 exclusions.
- 530 unique source evolution edges, 57 involving explicit form rows.
- Included alternate activation totals: 142 transformation, 4 field-dependent, 13 battle-state, and 188 intrinsic.

The implementation must fail if the pinned inputs derive different counts until that discrepancy is reviewed; it must not rewrite expected counts to make a test pass.

---

### Task 1: Production-valid source transport and phase catalog

**Files:**
- Modify: `requirements.in`
- Modify: `requirements.lock`
- Modify: `config/sources.yaml`
- Modify: `src/pokemon_league/sources/snapshot.py`
- Modify: `src/pokemon_league/sources/catalog.py`
- Modify: `src/pokemon_league/sources/bundle.py`
- Modify: `src/pokemon_league/sources/validate.py`
- Create: `src/pokemon_league/sources/semantic.py`
- Modify: `src/pokemon_league/cli.py`
- Test: `tests/sources/test_transport.py`
- Test: `tests/sources/test_semantic.py`
- Test: `tests/sources/test_catalog.py`
- Test: `tests/sources/test_bundle.py`
- Test: `tests/integration/test_production_sources.py`

**Interfaces:**

```python
class Phase(str, Enum): ...

class FetchedPayload(BaseModel):
    payload: bytes
    status: int
    final_url: str
    content_type: str
    etag: str | None

class SourcePin(BaseModel):
    kind: str
    value: str
    resolved_tree: str | None

class SemanticValidation(BaseModel):
    validator_id: str
    passed: bool
    facts: dict[str, str | int | bool]

def validate_source_payload(spec: SourceSpec, fetched: FetchedPayload) -> SemanticValidation: ...
def verify_source_bundle(..., phase: Phase) -> VerifiedSourceBundle: ...
```

- [ ] **Step 1: Write RED transport and trust tests**

Require a per-client `truststore.SSLContext`, `CERT_REQUIRED`, hostname checking, bounded reads/retries, response closure, exact final-host policy, and no call to `truststore.inject_into_ssl`. Cover wrong MIME, oversize payloads, redirects to undeclared hosts, 200-status challenge shells, and optional versus required failures.

- [ ] **Step 2: Write RED catalog/ledger binding tests**

Replace the global `required` policy with explicit phase relevance and `required_for`. Preserve pins in `SourceRecord`. Use bundle-relative `blobs/<sha256>` paths. Require an exact versioned ledger envelope containing phase, records, and optional coverage gaps. Offline verification must compare every record field and pin to its catalog row and rerun semantic validation from blob bytes.

- [ ] **Step 3: Implement native-trust HTTPS without weakening TLS**

Lock `truststore==0.10.4` with hashes. Pass `truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)` to the application transport; do not globally inject it. Validate before publishing a blob. A failed optional source becomes a sorted coverage gap; a failed required source aborts without a ledger. Staging and finalization must not allow invalid or orphan blobs into a verified bundle.

- [ ] **Step 4: Replace mutable/weak technical URLs**

Foundation-required inputs must include:

- `https://api.github.com/repos/smogon/pokemon-showdown/commits/b22742debfdce6e640193384f5731b9030f9cb6e`
- `https://codeload.github.com/smogon/pokemon-showdown/tar.gz/b22742debfdce6e640193384f5731b9030f9cb6e`
- raw `FORMES.md`, `SIMULATOR.md`, and `TEAMS.md` at that commit
- `https://windswaves.pokemon.com/en-us/?pubDate=20260306`
- versioned `https://cdn.jsdelivr.net/npm/@smogon/calc@0.11.0/package.json` for mechanics provenance

Keep human-facing `pokemon.com` pages that return challenge shells here as optional citation gaps. Remove the live Showdown directory index and GitHub `blob/master` pages as machine inputs. Record publication dates where supportable.

- [ ] **Step 5: Implement source-specific semantic validators**

The commit API must match exact commit, tree, and cutoff timestamp. The archive validator rejects absolute/traversal paths, symlinks, hardlinks, special files, duplicate NFC/case-folded paths, unexpected top-level prefixes, excessive member counts, and excessive expanded size; it requires the exact roster/mechanics files. Winds/Waves must contain the exact configured provisional names. Package metadata must contain exact package/version. HTML validators reject `Request unsuccessful`/challenge shells and require source-specific visible markers.

- [ ] **Step 6: Run the live Foundation source gate**

```bash
.venv/bin/pokemon-league sources snapshot --catalog config/sources.yaml --output work/sources-production --phase foundation --cutoff 2026-08-14
.venv/bin/pokemon-league sources verify --ledger work/sources-production/source-ledger.json --catalog config/sources.yaml --phase foundation --cutoff 2026-08-14 --offline
```

Expected: required records are semantically valid and checksum-valid; inaccessible optional official records are named gaps; no challenge payload is verified.

- [ ] **Step 7: Verify and commit**

Run source/integration tests, full pytest, Ruff, mypy, hash-required install, installed CLI help, and `git diff --check`.

Commit: `feat: verify production pokemon sources`

---

### Task 2: Pinned Showdown candidate extractor and explicit identity schema

**Files:**
- Create: `tools/extract_showdown_data.mjs`
- Create: `src/pokemon_league/roster/showdown_extract.py`
- Create: `src/pokemon_league/roster/candidates.py`
- Modify: `src/pokemon_league/schemas/roster.py`
- Modify: `src/pokemon_league/cli.py`
- Test: `tests/roster/test_showdown_extract.py`
- Test: `tests/roster/test_candidates.py`
- Test: `tests/fixtures/roster/showdown-mini/`
- Test: `tests/integration/test_production_candidates.py`

**Interfaces:**

```python
class SourceFormCandidate(BaseModel):
    source_form_id: str
    source_species_id: str
    combatant_id: str
    base_species_id: str
    evolution_node_id: str
    national_number: int | None
    display_name: str
    form_name: str | None
    form_class: str
    form_sort_order: int
    form_sort_source_id: str
    source_properties: dict[str, JsonValue]
    source_ids: tuple[str, ...]
    source_blob_hashes: tuple[str, ...]
    candidate_fingerprint: str

class CandidateAudit(BaseModel): ...
class SourceEvolutionRelation(BaseModel): ...
```

- [ ] **Step 1: Write RED safe-extraction tests**

The Python boundary accepts only the semantically verified pinned archive. The JS helper receives exact source bytes through a controlled boundary, executes no network or child process, exposes no host `process`/`require` to evaluated upstream data, enforces a timeout, rejects accessors/functions where literal data is required, and returns only deeply validated JSON primitives. Tests include traversal archives, symlinks, duplicate normalized paths, unexpected prefixes, code-execution attempts, duplicate object IDs, and nondeterministic source ordering.

- [ ] **Step 2: Add explicit identity fields**

Separate `source_species_id`, National `base_species_id`, public `combatant_id`, and `evolution_node_id`. Add `form_class`, source-derived sort order, all original source order slots, source fingerprints, and exact blob provenance. Do not use one field for multiple identity roles.

- [ ] **Step 3: Extract the complete candidate universe**

Accept positive National numbers 1–1025 only. Put num 0, negative/CAP/Pokéstar, and positive numbers above cutoff in a source-scope audit, never in the roster. Require exactly one base identity for each number; #1 is Bulbasaur and #1025 is Pecharunt. Expand and deduplicate all `cosmeticFormes`. Add class-level exclusion candidates for non-enumerable cosmetic systems such as Spinda spots and Alcremie decorations without pretending each appearance is enumerated.

- [ ] **Step 4: Add provisionals through official evidence only**

Add exactly Browt, Pombon, and Gecqua from the verified reveal adapter. They are unnumbered and carry no inherited stats, moves, Ability, type, evolution, or mechanics eligibility.

- [ ] **Step 5: Derive stable ordering and relations**

Respect `formeOrder`, retaining repeated source slots but using the first valid slot for scalar order. Discover the 34 Gmax rows absent from `otherFormes`/`formeOrder` through their own metadata and append deterministically. Preserve all `prevo`/`evos` relations as form-specific source relations before decisions.

- [ ] **Step 6: Run the production extraction cross-check**

```bash
.venv/bin/pokemon-league roster extract --sources work/sources-production --output work/roster-production
```

Expected derived cross-check: 1,380 positive raw rows, 1,025 bases, 355 raw alternates, 89 generated cosmetics, 3 provisionals, 1,472 total candidates, and 530 unique source evolution edges including 57 form-edge relations. Any difference blocks rather than changes the expectation.

- [ ] **Step 7: Verify and commit**

Run focused/golden/permutation tests, full pytest, Ruff, mypy, Node 22 runtime check, CLI help, and diff check.

Commit: `feat: extract complete pokemon roster candidates`

---

### Task 3: Evolution nodes, activation requirements, and profile/equivalence proofs

**Files:**
- Modify: `src/pokemon_league/schemas/roster.py`
- Modify: `src/pokemon_league/roster/builder.py`
- Modify: `src/pokemon_league/roster/evolution.py`
- Modify: `src/pokemon_league/roster/equivalence.py`
- Modify: `src/pokemon_league/roster/validate.py`
- Create: `src/pokemon_league/roster/profile_resolution.py`
- Create: `src/pokemon_league/roster/equivalence_proof.py`
- Test: `tests/roster/test_production_evolution.py`
- Test: `tests/roster/test_profile_resolution.py`
- Test: `tests/roster/test_equivalence_proof.py`

- [ ] **Step 1: Write RED evolution-node tests**

Require Bulbasaur → Ivysaur → Venusaur stages 1–3; Mega/Gmax Venusaur inherit Venusaur's node/stage; Kanto Meowth → Persian, Alolan Meowth → Alolan Persian, and Galarian Meowth → Perrserker remain separate branches; Pikachu has sourced Raichu and Alolan Raichu branches; Eevee's branches are complete. Production rejects empty/incomplete relations and any included non-root node without sourced predecessor coverage.

- [ ] **Step 2: Operate evolution mapping on `evolution_node_id`**

Persistent regional/evolution branches use form-specific nodes. Mega, Primal, Gmax, fused/temporary transformations, and ordinary battle states inherit the biological source node and stage. Compile edges only after decisions; preserve excluded relations in the audit. Require normalized `prevo` and `evos` agreement except an exact reviewed override.

- [ ] **Step 3: Preserve complete activation requirements**

Replace the lossy single item-or-condition field with a typed structure that can preserve item alternatives, required move, required Ability, starting field/weather/terrain, timer, battle-state trigger, and other explicit conditions. Arceus must retain both item alternatives per typed form. Gmax proof carries HP scaling, weight immunity, move replacement, and three-turn timer rather than trusting placeholder stats/weight.

- [ ] **Step 4: Correct legality and excluded-decision invariants**

`core_series_player_legal` and `official_player_controllable` are independent except boss-only false/false. Excluded decisions have nullable activation/equivalence/profile fields and require only exact exclusion provenance/reason. Production Foundation lore status remains `insufficient` until a lore overlay proves dossier completeness.

- [ ] **Step 5: Resolve technical turn-based profiles**

Resolve stats, types, gender restrictions, weight, Ability choices, full learnset/event restrictions, required objects, state rules, and Champions precedence from the pinned sources. Hash the complete normalized proof. A form is `complete_turn_based` only when every field and referenced rule resolves. Eternamax uses its exact dedicated boss proof. Fourteen flagged Mega identities remain `realtime_only` unless an official compatible turn-based source proves otherwise: Absol-Mega-Z, Garchomp-Mega-Z, Lucario-Mega-Z, Heatran-Mega, Darkrai-Mega, Zygarde-Mega, Golisopod-Mega, Magearna-Mega, Magearna-Original-Mega, Zeraora-Mega, the three Tatsugiri Megas, and Baxcalibur-Mega.

- [ ] **Step 6: Require proof before equivalence collapse**

Default every included candidate to unique game and lore groups. A game group may merge only identical full profile/build-space/state fingerprints with a saved proof. A lore group may merge only identical anatomy/behavior/power/habitat/evidence fingerprints; without dossiers it remains unique. Track proof records name the canonical member and differing/identical fields. Administrative-flag equality alone is never proof.

- [ ] **Step 7: Verify and commit**

Run regional/branch/property tests, full pytest, Ruff, mypy, deterministic proof serialization, and diff check.

Commit: `feat: prove roster evolution and profiles`

---

### Task 4: Materialize and independently review every form decision

**Files:**
- Create: `config/roster-classification-rules.yaml`
- Replace: `config/roster-decisions.csv`
- Create: `config/roster-decision-overrides.csv`
- Modify: `config/roster-decisions.md`
- Create: `src/pokemon_league/roster/decision_compiler.py`
- Modify: `src/pokemon_league/roster/loader.py`
- Test: `tests/roster/test_decision_compiler.py`
- Test: `tests/integration/test_production_decisions.py`

- [ ] **Step 1: Write RED coverage and precedence tests**

Rules generate proposals, never final decisions. Unmatched candidates remain `pending`; there is no default include/exclude. Candidate IDs must equal decision IDs exactly, fingerprints must match, and duplicate/stale/missing rows fail. Exact boss/provisional overrides run before cosmetics/encounter modifiers, transformations/states, and intrinsic distinctions.

- [ ] **Step 2: Implement deterministic proposal compilation**

Materialize `candidate_fingerprint`, `rule_id`, source IDs, inclusion/exclusion rationale, activation requirements, legality flags, historical/profile statuses, and proposed equivalence groups. Included rows require verified provenance and rationale. Excluded rows require stable reason code/text and no fabricated activation/profile values.

- [ ] **Step 3: Apply the frozen classification audit**

The expected reviewed partition is 1,375 included / 97 excluded over 1,472 candidates. Exclude the 89 generated cosmetics and these eight raw rows: Xerneas-Neutral, Mimikyu-Busted, Mimikyu-Busted-Totem, Sinistea-Antique, Polteageist-Antique, Poltchageist-Artisan, Sinistcha-Masterpiece, and Zarude-Dada.

Include the 11 historically player-controllable Totem size forms without encounter aura/stat boosts. Preserve Totem size/weight/Ability distinctions, mark them historical, and never mark them boss-only.

- [ ] **Step 4: Review every edge category independently**

Use read-only reviewers for:

1. base/regional/gender/size/appliance identities;
2. 97 Mega, 34 Gmax, Primal, fusions/riders, Crowned, and named Tera transformations;
3. field-dependent and 13 battle-state identities;
4. cosmetics, authenticity, encounter modifiers, spent markers, and unsupported variant classes;
5. historical, event, Champions-only, and 2026 profiles.

The integrator alone applies findings. Save reviewer summaries/hashes under `work/roster-production/reviews/` and record their digest in the final decision audit.

- [ ] **Step 5: Manually prove the semantic edge set**

Review the 22 same-core-property rows called out by the audit: Cherrim-Sunshine; Keldeo-Resolute; four Genesect Drives; Vivillon Fancy/Poké Ball; Magearna-Original; Cramorant Gulping/Gorging; Morpeko-Hangry; Squawkabilly-Blue; Tatsugiri Droopy/Stretchy; and the seven raw exclusions other than Mimikyu-Busted-Totem. Also review all Cosplay/costume/cap/Partner/World Pikachu identities and Spiky-eared Pichu from form-specific move/event legality. Do not collapse Squawkabilly, Tatsugiri, cap Pikachu, Magearna colors, or other candidates without saved track proof.

- [ ] **Step 6: Assert the activation partition**

The 347 included raw alternates derive exactly 142 transformations, 4 field-dependent forms, 13 battle states, and 188 intrinsic forms. The 13 battle states are Darmanitan Zen, Galarian Darmanitan Zen, Meloetta Pirouette, Ash-Greninja, Aegislash Blade, Zygarde Complete, Wishiwashi School, Minior Meteor, Cramorant Gulping/Gorging, Eiscue Noice, Morpeko Hangry, and Palafin Hero.

- [ ] **Step 7: Verify and commit**

Run decision coverage, shuffle determinism, stale-fingerprint, exact partition, full pytest, Ruff, mypy, and diff check. Confirm no synthetic marker appears in production inputs.

Commit: `data: audit every pokemon form decision`

---

### Task 5: Real cutoff build and clean-room Foundation receipt

**Files:**
- Modify: `src/pokemon_league/roster/validate.py`
- Modify: `src/pokemon_league/cli.py`
- Create: `src/pokemon_league/phases/receipt.py`
- Test: `tests/integration/test_production_roster.py`
- Test: `tests/integration/test_foundation_receipt.py`
- Preserve: `tests/integration/test_roster_cutoff.py` as explicitly synthetic/test-only

- [ ] **Step 1: Write RED production identity tests**

Production validation requires exact National identity mapping, not cardinality alone; source/extraction hashes must prove one base identity per number; synthetic source kinds/names/rationales are forbidden; candidate/decision sets and fingerprints are one-to-one; evolution relations are nonempty/complete; every complete game profile and alias has a proof; all Foundation-required sources are semantically verified.

- [ ] **Step 2: Bind derived artifacts to frozen inputs**

The extraction manifest records source archive/API/reveal hashes, extractor/schema version, candidate/edge hashes and counts, and Node/Python runtime identities. The build consumes and hashes the same bytes it parses. Reopening a mutable path later cannot change the recorded input hash. Optional gaps propagate unchanged into audit/receipt.

- [ ] **Step 3: Publish the real roster transactionally**

```bash
.venv/bin/pokemon-league roster build \
  --sources work/sources-production \
  --raw-forms work/roster-production/raw-forms.json \
  --edges work/roster-production/evolution-edges.json \
  --decisions config/roster-decisions.csv \
  --output outputs \
  --audit work/roster-production/roster-audit.json \
  --require-cutoff-counts
```

Expected: deterministic `combatants.parquet`, `combatants.csv`, `excluded-forms.csv`, and audit; 1,025 base species and three provisionals; candidate/include/exclude counts match reviewed artifacts; no production claim is made from the synthetic fixture.

- [ ] **Step 4: Write the phase receipt**

Receipt fields include git commit, cutoff/timezone, catalog/ledger hashes, required IDs/optional gaps, upstream commit/tree, schema/extractor/profile/decision versions, candidate/decision/evolution counts and hashes, combatant/exclusion/canonical-universe counts, output hashes, Python/Node lock hashes, exact command-log hash, limitations, and `passed` only after every gate.

- [ ] **Step 5: Prove clean-checkout reproducibility**

From a clean worktree and the same frozen local source bundle, run install, offline source verify, extraction, decision verify, roster build, receipt, full tests, Ruff, and mypy twice. Require byte-identical roster artifacts and matching receipts apart from explicitly excluded run timestamp fields.

- [ ] **Step 6: Commit and open downstream gates**

Commit: `feat: publish verified all pokemon roster`

Only after independent broad review approves the cumulative Foundation diff and `work/phase-receipts/foundation-roster.json` is `passed` may the mechanics and lore plans begin.

## Production source and publication commands

```bash
.venv/bin/pip-compile --generate-hashes --output-file requirements.lock requirements.in requirements-dev.in
.venv/bin/pip install --require-hashes -r requirements.lock
.venv/bin/pokemon-league sources snapshot --catalog config/sources.yaml --output work/sources-production --phase foundation --cutoff 2026-08-14
.venv/bin/pokemon-league sources verify --ledger work/sources-production/source-ledger.json --catalog config/sources.yaml --phase foundation --cutoff 2026-08-14 --offline
.venv/bin/pokemon-league roster extract --sources work/sources-production --output work/roster-production
.venv/bin/pokemon-league roster decisions verify --candidates work/roster-production/source-form-candidates.json --decisions config/roster-decisions.csv
.venv/bin/pokemon-league roster build --sources work/sources-production --raw-forms work/roster-production/raw-forms.json --edges work/roster-production/evolution-edges.json --decisions config/roster-decisions.csv --output outputs --audit work/roster-production/roster-audit.json --require-cutoff-counts
.venv/bin/pokemon-league phase receipt --phase foundation-roster --output work/phase-receipts/foundation-roster.json
```

## Phase risks to preserve in the receipt

- Official pages may be inaccessible behind anti-bot controls; list them as gaps instead of treating challenge shells as evidence.
- The frozen technical source is not first-party canon and must remain labeled.
- Mutable official context cannot be bit-reacquired without the local frozen bundle; raw copyrighted material is intentionally not republished.
- Form inclusion and equivalence can be wrong if automated proposals are mistaken for decisions; independent category review is mandatory.
- The npm registry TLS failure in this environment does not authorize alternate unpinned packages or insecure TLS. Package installation remains separately integrity-locked.
- Candidate counts are derived acceptance checks, never a substitute for identity, provenance, decision, evolution, profile, and alias proof.
