# All-Pokémon Battle League Design

**Status:** Approved conversational design; awaiting review of this written specification

**Date:** August 14, 2026

**Evidence cutoff:** August 14, 2026, America/Chicago

**Primary audience:** General Pokémon reader (`product stakeholders` report shape)

**Primary delivery mode:** Portable HTML report with queryable supporting datasets

## 1. Goal

Determine which Pokémon would perform best against every other Pokémon under two separately defined systems:

1. A standardized one-on-one game-mechanics model.
2. A lore-and-animation realism model that respects species behavior and fighting style.

The analysis must account for every released National Pokédex species, every evolutionary stage, and every combat-relevant form. It must expose all unique pairwise results, compare every evolution family internally, name separate game and lore champions, and provide a clearly labeled combined consensus result.

The result is an exhaustive model-conditioned answer, not a claim that Pokémon canon supplies one objectively provable universal winner.

## 2. User-approved constraints

- Game mechanics and lore/anime realism are separate tracks.
- Combat-relevant forms compete separately.
- No trainers, teammates, switching, outside assistance, or ordinary held items.
- Each Pokémon may use its best legal moves and natural abilities.
- An item or condition required to sustain a selected form is treated as part of that form.
- Required transformations begin active.
- Victory is by fainting in the game track and incapacitation in the lore track.
- Evolutions are independent contestants and receive no automatic advantage.
- The analysis uses a tiered hybrid: every pairing receives a transparent analytical decision, while close, complex, upset, and ranking-sensitive fights receive deeper simulation or evidence review.

## 3. Reporting job

### Question

Which Pokémon beats the largest share of all other Pokémon under standardized game mechanics, under lore/anime realism, and under an explicitly labeled 50/50 consensus of those tracks?

### Decision-useful answer

The report must let the reader identify:

- the unrestricted game champion;
- the player-legal game champion;
- the lore/anime champion;
- whether either track has a true Condorcet winner;
- the combined consensus leader when both tracks are available;
- any material disagreement among those answers;
- the result and decisive factors for any requested pairing; and
- the internal ordering of every evolution family.

### Scope and baseline

- Roster and evidence are current through August 14, 2026.
- One healthy Pokémon or form fights one other healthy Pokémon or form.
- Game fights use a neutral field unless a combatant changes it.
- Lore fights use a mixed neutral environment plus one viable home environment for each combatant.
- The full unordered comparison basis is `N * (N - 1) / 2` for each track's eligible roster.

### Success criteria

The work is decision-useful when every eligible entrant and unique pair is accounted for, the result can be reproduced from pinned inputs, important uncertainty is visible, and the user can look up both a summary winner and individual fights such as Bulbasaur versus Ivysaur or Bulbasaur versus Venusaur.

## 4. Contestant manifest

The final form count is generated from a validated manifest rather than typed into the narrative. Each row has a stable `combatant_id`, base National Pokédex species, display name, form name, evolution family and stage, release status, source version, `mechanics_eligible`, `lore_evidence_status`, `core_series_player_legal`, `official_player_controllable`, form activation class and rule, required form item or condition, `game_profile_status`, `game_equivalence_group`, `lore_equivalence_group`, `game_canonical_combatant_id`, `lore_canonical_combatant_id`, `consensus_canonical_combatant_id`, and inclusion rationale.

The roster has two frozen species-count assertions at this cutoff: exactly 1,025 released numbered species, Bulbasaur through Pecharunt, and exactly three officially revealed provisional unnumbered species, Browt, Pombon, and Gecqua. The form count is derived only after the per-track equivalence rules run.

`core_series_player_legal = true` means a core-series game allowed the player to field that species or form, including a player-triggered temporary transformation. `official_player_controllable = true` extends that definition to official battle titles such as Pokémon Champions. Boss-only, cutscene-only, unreleased, and otherwise non-controllable forms are false for both fields. A historical but once controllable form remains player-controllable and is also tagged `historical`. The report's "player-legal champion" uses the `official_player_controllable` field and explains that label once.

`game_profile_status` is one of `complete_turn_based`, `realtime_only`, `incomplete`, or `not_applicable`. Only `complete_turn_based` contestants enter the mechanics and consensus brackets. A Z-A-only form remains present in the manifest and lore work but receives no translated or inherited turn-based profile until Pokémon Champions or another official turn-based source supplies its stats, Ability behavior, and legal moves.

`lore_evidence_status` is one of `complete`, `limited`, or `insufficient`. Complete and limited dossiers may enter the lore bracket with their resulting confidence grade; insufficient dossiers produce unavailable pair records and do not enter rankings.

Form activation is classified as:

- `intrinsic` — a persistent selectable identity such as a regional or appliance form;
- `transformation` — a named preactivated form such as Mega, Primal, Gigantamax, or the approved species-specific Tera exceptions;
- `field_dependent` — a form such as Castform or Cherrim that requires weather or terrain; or
- `battle_state` — a threshold- or event-triggered state such as Zen, School, Complete, Core, Hero, or Noice.

The selected identity is instantiated at full HP and free of status, so activation prerequisites are waived at time zero as the user approved. In the mechanics track, the first ordinary engine form check then applies canonical reversion or transition rules. A sole field-dependent entrant supplies its required starting field. If both entrants require the same field, that field starts active. If their requirements conflict, the field starts neutral, both selected identities exist at time zero, and the first canonical form check may revert either or both before they act. The matchup record flags this conflict. Lore activation follows the separate evidence-duration and arena-weather rule in Section 7.4.

Per-track equivalence is explicit. Forms in the same `game_equivalence_group` reuse one mechanics result only when all modeled battle properties and legal options are identical. Forms in the same `lore_equivalence_group` reuse one lore result only when anatomy, size, behavior, powers, habitat, and evidence are also equivalent. Each group has exactly one canonical combatant ID selected by the lowest National number, then official form order, then stable ID. Alias rows point to that ID, remain searchable, and are excluded from that track's pair generation and ranking. A variant may therefore be a game alias but a separate lore entrant, or the reverse. Sex-specific or color-specific variants survive only in the tracks where a real difference exists.

Consensus equivalence collapses two entries only when they share both the game and lore canonical IDs. Otherwise each retains a distinct `consensus_canonical_combatant_id`; its consensus calculation looks up the appropriate canonical result in each underlying track. This prevents cosmetic duplicates without erasing a difference that exists in only one track.

### 4.1 Included contestants

- Every released, numbered National Pokédex species, including every evolutionary stage.
- Regional forms and combat-distinct breeds.
- Sex, size, appliance, style, Drive, Plate, Memory, mask, and comparable forms when stats, typing, Ability, movepool, weight, or another battle property differs.
- Every Mega Evolution, including X/Y/Z variants and forms introduced through Pokémon Legends: Z-A, Mega Dimension, and Pokémon Champions by the evidence cutoff. A form without a complete released turn-based profile is mechanics-ineligible rather than guessed.
- Primal Groudon and Primal Kyogre.
- Origin, Crowned, Unbound, Sky, fused, rider, and other battle-distinct named forms.
- Every Gigantamax form because it changes appearance and provides a species-specific G-Max move.
- Named in-battle forms such as Aegislash Blade, Darmanitan Zen, Wishiwashi School, Zygarde Complete, Palafin Hero, Minior Core, Eiscue Noice, Ogerpon's named Tera aspects, and Terapagos Terastal/Stellar. They begin in the selected form and retain canonical timers, drawbacks, transition rules, and reversion rules.
- Historical battle-distinct forms when official battle data exists. These are labeled `historical` rather than silently treated as current player-legal options.
- Eternamax Eternatus as the explicit boss-form allowlist at this cutoff, with both player-legality fields false. Adding another boss form requires a named official form identity, a distinct official battle profile, and a manifest-rule revision; encounter scaling, raid multipliers, auras, Totem boosts, Titan boosts, and Noble frenzy effects remain excluded.
- Officially revealed but unreleased Pokémon Browt, Pombon, and Gecqua as provisional manifest entries. Their game result remains unavailable until official turn-based stats and learnsets exist; their lore eligibility depends on the dossier-completeness gate in Section 7.3. No values are invented.

### 4.2 Excluded as separate contestants

- Shiny coloration and cosmetic-only patterns, flowers, seasons, trims, decorations, authenticity marks, and equivalent appearance variants.
- Generic Dynamax, ordinary Terastallization, and Z-Moves because they are universal battle modifiers rather than Pokémon identities.
- Temporary appearance or spent-Ability markers such as Mimikyu Busted when they have no distinct stats, typing, move access, or independently selectable transformation profile. They arise naturally during the corresponding Pokémon's fight. A battle state such as Eiscue Noice remains separate because its official stat profile changes.
- Alpha, Titan, Noble, raid-boss, aura, Shadow/Purified, and comparable encounter modifiers.
- Team-dependent variants whose distinction has no solo-battle effect.

Every exclusion is retained in a machine-readable exclusion table with a reason. No form is silently dropped.

## 5. Shared fight rules

- One entrant per side.
- Both begin healthy, free of status, and aware that a fight has begun.
- Neither has a trainer, teammate, or outside support.
- Neither switches or leaves to reset a form or Ability.
- Both may use four legal moves selected under the track-specific policy.
- Required form conditions are active at the start. The mechanics track applies engine-defined turn timers, item behavior, and reversion checks. The lore track instead uses duration, exhaustion, and sustaining conditions from the selected continuity evidence; a three-turn game abstraction is never silently imported into animation realism.
- An entrant that permanently flees and refuses to reengage loses in the lore track.
- If neither side can meaningfully threaten the other, the result is a draw rather than a forced winner.

## 6. Game-mechanics track

### 6.1 Rules freeze

The game track is a custom all-era composite. No official released title contains every historical species and form under one engine. Every mechanics fight runs in one shared pinned turn-based engine: the Pokémon Showdown Champions mod with the project's explicit one-on-one custom rules. A battle never runs one side under one generation's engine and the opponent under another.

The shared engine uses a versioned per-form override table for species stats, typing, Abilities, learnsets, required-item behavior, and named transformations. For a form with a complete Pokémon Champions profile, Champions data takes precedence. Otherwise, the most recent compatible official turn-based main-series profile available by the cutoff is mapped into the shared engine. Legacy moves use their shared-engine behavior, not their historical-generation behavior. Any field that lacks a compatible official mapping makes that form mechanics-ineligible instead of triggering an inference.

The standard entrant has:

- level 100 under the standard current-generation level-dependent stat and damage formulas explicitly enabled in the custom format;
- 31 IVs in all six stats;
- zero trained EVs or Stat Points;
- a neutral nature;
- the best legal natural Ability available to that form;
- four moves selected from its complete legal learnset; and
- no ordinary held item.

This represents a prime natural specimen while avoiding trainer-created stat specialization. Move and Ability selection may vary by matchup, but both sides select simultaneously from candidate builds; neither counterpicks after observing the other's final build.

The complete legal learnset is the union accepted by the pinned custom National Dex validator after applying form, event, transfer, and move-combination restrictions. A move is not admitted merely because the base species learned it in some title; it must be legal on the selected form and compatible with the rest of that build. Newly released Champions-era forms use their released Champions learnset until a later official source expands it. Regression fixtures verify the level-100 stat and damage formulas rather than inheriting an implicit level-50 Champions default.

The custom format does not inherit Smogon tier bans on otherwise legal moves, Abilities, sleep, evasion, or one-hit-knockout effects. Moves that require an ally, bench, switching, or a defeated teammate are removed or marked ineffective in this solo format. Entry hazards and phazing receive no value when they cannot affect a one-Pokémon side.

Generic Dynamax, ordinary Terastallization, and Z-Moves are disabled. Ogerpon's named Tera aspects and Terapagos Terastal/Stellar are explicit contestant exceptions: they begin in the selected official type/form, receive only that form's released Ability activation and special STAB rules, persist for the official full-battle duration, and cannot invoke another Tera action. Their exact overrides are pinned and fixture-tested.

Gigantamax entrants begin Gigantamaxed at Dynamax Level 0, reflecting no Dynamax Candy training. They receive the official 1.5× maximum-HP scaling, use Max or species-specific G-Max replacements for their four base moves for three turns, and then revert with current HP adjusted by the official proportional rule.

A form-required item occupies the item slot and retains every effect inseparable from the official form, including type, move, Ability, or damage modifiers. It cannot be removed, swapped, consumed, stolen, or flung unless the originating official rules explicitly permit that interaction. Knock Off, Trick, Switcheroo, Fling, Poltergeist, and related moves follow the pinned per-item override table. No contestant receives a second ordinary item.

Game victory requires fainting. Temporary sleep, freeze, trapping, or inability to act is not by itself a win. A simultaneous knockout is a draw. A battle still unresolved after 200 turns is a loop draw.

### 6.2 Candidate builds

The build generator creates legal one-on-one archetypes rather than copying six-on-six usage sets. Candidate roles include:

- physical, special, and mixed immediate attackers;
- priority and speed-control attackers;
- setup attackers;
- status and recovery plans;
- anti-setup plans;
- fixed-damage and Endeavor plans;
- Counter, Mirror Coat, and Metal Burst plans;
- trapping and Perish Song plans when independently functional; and
- PP-pressure or stall plans that can terminate within the turn cap.

It removes dominated attacks only when type, category, power, accuracy, priority, targeting, secondary effect, and relevant contact properties make the removed move no better in any modeled state. Strategic exceptions are preserved.

Every ordinary generated build is checked through the pinned team validator. The simulator alone is not treated as proof of legality. Eternamax Eternatus uses a separate boss-profile validator: its stats, Ability, item state, and four-move build must exactly match the pinned official encounter profile and cannot inherit base Eternatus learnset legality or enter alternate-build generation.

For every pair, the initial finite payoff matrix contains at most 16 validated nondominated builds per combatant: the strongest applicable build from each archetype plus no more than four matchup-specific counter builds. Ability choice is part of a build. Both sides generate candidates from the visible opponent species and form, but neither sees the other side's final selection. The analytical payoff matrix is solved as a simultaneous zero-sum game; its equilibrium mixture supplies the ordinary pair's build distribution. Escalated double-oracle search may add one best response per side per iteration, up to 20 iterations and an absolute cap of 36 builds per side.

To avoid circularly requiring a trained surrogate before selecting its own training builds, calibration starts with a bootstrap payoff matrix. Each build pair's bootstrap payoff is the Section 6.3.1 continuation value from the standardized opening state, converted from `[-1, 1]` to expected score `[0, 1]`. That matrix selects the first equilibrium mixtures for the 10,000 calibration pairs. After the surrogate is fitted, every matrix is re-solved. Fit or temperature-validation pairs whose equilibrium expected score changes by more than five percentage points are simulated once more and the surrogate receives one final refit. The conformal partition does not influence the refit decision and is evaluated only after the final predictor and temperature are frozen. The second fit is frozen even if smaller residual changes remain, and those residuals are included in the model interval.

### 6.3 Tiered matchup process

Every unique pairing receives an analytical pass that evaluates:

- type effectiveness and immunities;
- Ability interactions;
- speed, priority, and likely move order;
- damage ranges and knockout tempo;
- accuracy and critical-hit exposure;
- recovery, status, setup, and stat reset options;
- fixed-damage and retaliation moves;
- form timers and transformations; and
- loop or mutual-inability conditions.

The analytical pass uses a frozen multinomial surrogate to produce modeled `P(win)`, `P(draw)`, and `P(loss)` values that sum to one. Its features are generated from the candidate-build equilibrium and include damage-based knockout turns, survival margins, speed and priority control, accuracy exposure, recovery, setup, status, fixed damage, retaliation, immunity and bypass tags, form duration, PP pressure, and loop risk.

Before the exhaustive scoring run, the surrogate is trained on a fixed stratified sample of 10,000 roster pairs. Sampling covers deciles of the two sides' fastest expected knockout-turn differential, base-stat-total deciles, generations, form classes, type combinations, and every rare-interaction tag. The knockout-turn premeasure uses each side's best legal damaging route under mean damage and accuracy, with status and setup omitted only for that sampling stratum. Each sampled pair runs 256 paired seeds, with one battle in each player position per seed.

The frozen split is 7,000 fit pairs, 1,500 temperature-validation pairs, and 1,500 untouched split-conformal calibration pairs. Temperature is fitted only on the validation partition; conformal residuals are computed only after the predictor and temperature are frozen, using the untouched calibration partition. The feature schema, coefficients, split IDs, seeds, temperature, calibration diagnostics, and model hash are saved before any full-roster ranking is calculated. If the one allowed mixture-refit cycle runs, it preserves those pair partitions and again leaves the 1,500 conformal pairs unused until the refitted predictor and temperature are frozen.

This statistical surrogate does not replace rule logic. Hard immunities, impossible targeting, mandatory form changes, guaranteed one-hit outcomes, and proven loops are applied before the model and recorded as rule decisions. The analytical output includes modeled probabilities, a central expected score `S = P(win) + 0.5 * P(draw)`, its conformal interval, decisive factors, and an escalation flag.

#### 6.3.1 In-battle controller

Every simulated combatant uses the same open-set controller. It may inspect the full current battle state, both selected move sets, Abilities, form rules, stat stages, status, remaining HP, and remaining PP. It cannot inspect the future random seed or future damage, accuracy, critical-hit, status-duration, or secondary-effect outcomes.

On each turn, the controller builds a zero-sum matrix over both sides' legal actions. Its depth-three full-turn recurrence is:

- `V_0(state) = H(state)`, where `H` is the normalized heuristic below.
- `Q_d(state, action_A, action_B) = sum(probability(outcome) * V_(d-1)(next_state))` for `d` from 1 through 3.
- `V_d(state)` is the zero-sum equilibrium value of the legal-action matrix `Q_d`.
- A terminal state returns 1 for an A win, -1 for an A loss, or 0 for a draw at every depth.

There is no discounting. Chance branches come from the pinned engine. When a joint action has at most 4,096 distinct three-turn chance paths, the controller enumerates them exactly. Otherwise it uses 256 deterministic counter-based samples keyed by state hash, joint action IDs, depth, and controller version—not by the unseen battle seed—and averages those leaf values. The normalized leaf heuristic is:

`0.50 * HP advantage + 0.20 * expected damage-tempo advantage + 0.10 * action-order advantage + 0.10 * status/control advantage + 0.10 * boost/recovery/PP advantage`.

Each component is bounded from -1 to 1. HP advantage is A's current-HP fraction minus B's. Damage-tempo advantage is `clamp((B-to-A expected KO turns - A-to-B expected KO turns) / 10, -1, 1)`. Action-order advantage is 1 when A's selected action resolves first, -1 when B's does, and 0 for a true tie after priority and speed. Status/control gives incapacity this turn a severity of 1.00; sleep or freeze 0.75; toxic 0.50; paralysis, burn, or ordinary poison 0.25; and each active confusion, trapping, seed, or comparable volatile 0.15, with each side capped at 1.00 before subtraction. Boost/recovery/PP advantage is the mean difference of normalized relevant stat stages, immediately recoverable HP fraction, and remaining relevant PP fraction. A terminal win is 1, a terminal loss is -1, and a terminal draw is 0 regardless of the heuristic.

The controller solves the action matrix, samples from its equilibrium mixture using the battle seed, and repeats after the resulting state is observed. Exactly tied pure actions form a uniform mixture ordered by canonical action ID, making the seeded choice reproducible. Controller version and component functions are pinned and unit-tested.

#### 6.3.2 Escalation

A matchup escalates to seeded turn-by-turn simulation when any of these applies:

- the analytical interval includes 50%;
- the central estimate lies from 40% through 60%;
- two viable build archetypes reverse the predicted winner;
- a rare interaction is not covered by an analytical test;
- the pair's full uncertainty span is large enough to move either entrant into or out of the top 5% in the completed analytical leaderboard;
- it is an intra-evolution-family fight; or
- it is selected for finalist, upset, or audit coverage.

Escalation is multipass and independent of pair-processing order. Pass 1 scores every pair analytically and freezes the complete analytical leaderboard. Pass 2 simulates all flags derived from that frozen leaderboard, then recomputes scores. A further pass rechecks only pairs whose remaining interval can alter the champion or top-25 membership. The process stops when the champion and top-25 membership are unchanged and no unreviewed interval can reverse them, or after three escalation passes; reaching the cap with residual risk is disclosed.

Escalated fights run paired seeds, with one battle in each player position for every seed. They begin at 64 seed pairs, then increase to 256 and 1,024 while the confidence sequence includes 50% or the outcome remains ranking-sensitive. Finalist and champion-deciding fights may increase to 4,096 seed pairs. The sampling observation for one seed is the mean of its two seat-oriented battle scores, so it remains bounded from 0 to 1 without pretending the correlated seat battles are independent. Sampling uncertainty uses a two-sided 95% anytime-valid empirical-Bernstein confidence sequence over those paired-seed means, so adaptive stopping does not reuse an ordinary fixed-sample interval incorrectly.

Pair-specific double-oracle build search applies to finalist, champion-deciding, and build-reversal matchups. It iteratively adds exploitable best-response builds and resolves the simultaneous zero-sum build matrix until no discovered response changes either side's expected score by more than two percentage points or the iteration cap of 20 is reached. The manifest records which stop condition occurred.

### 6.4 Game result

Each pair stores:

- unordered pair key and both combatant IDs;
- winner, loser, or draw;
- expected score `S = P(win) + 0.5 * P(draw)` for each side;
- modeled or simulated win, loss, and draw probabilities that sum to one;
- conformal model interval for analytical rows or anytime-valid sampling interval for simulated rows;
- selected or mixed build IDs;
- decisive moves and interactions;
- analytical-versus-simulated method label;
- simulation count and seed schedule;
- termination reason;
- player-seat discrepancy check; and
- confidence grade.

If the final interval still contains 50%, the fight is labeled statistically unresolved for categorical winner and Copeland reporting. The primary expected-points ranking still uses the saved central expected score, while the uncertainty analysis tests whether any value inside the interval could change the champion. No categorical winner is forced.

## 7. Lore and animation track

### 7.1 Standard representative

Each entrant is a healthy, prime adult representative of its species or selected form. Normal temperament, intelligence, self-control, fear, and preferred distance remain intact. The combatant seeks incapacitation without artificial bloodlust.

Named, heavily trained anime Pokémon establish an upper bound rather than the ordinary species baseline. Population status is stored per `continuity_id` as `unique`, `multiple`, or `unknown`. A Legendary or Mythical uses its own direct feats as the central baseline only in a continuity that establishes that individual as unique; a different continuity that demonstrates multiple individuals uses a species-typical baseline. Exceptional named specimens never become the baseline solely because another continuity calls the species unique.

Each entrant has one opponent-independent primary four-move loadout that reflects repeated depicted behavior, signature moves, and its ordinary combat role. It may also have validated alternate capability loadouts drawn through the track-specific lore move resolver below. For a complete turn-based form, that resolver includes compatible TM, tutor, event, egg, and transfer moves accepted by the form validator. This is a deliberate capability convention under the user's "best legal moves" instruction; no trainer is present during the fight. In close cases, both sides' alternate loadouts are evaluated simultaneously, never by sequential counterpick.

Lore move resolution is independent of mechanics eligibility. A `complete_turn_based` form may reuse moves accepted by the pinned form-specific validator. A `realtime_only` form may use only moves explicitly shown or listed for that exact form in its released official title or another identified official work; it cannot inherit a base-form move merely because the names are related. An animation-only loadout may use moves directly demonstrated by an ordinary specimen in the selected continuity. An unreleased or provisional form with no four supportable moves may use only the smaller demonstrated set and normally fails the dossier-completeness gate. Every lore move stores its exact source and `lore_move_profile_status`; unsupported base-form inheritance is prohibited.

Once combat starts, the Pokémon knows the opponent's visible body, actions, and revealed powers but has no dossier-like foreknowledge. Pair-specific analytical loadout testing does not grant its in-fight behavior advance knowledge of an unrevealed immunity, move, or weakness.

Innate capabilities outside the four moves are limited to passive anatomy, locomotion, ordinary senses, continuous Ability effects, and biological functions explicitly described as always available. A deliberate named attack, projectile, status technique, or equivalent offensive feat occupies a move slot; it cannot be renamed as "anatomy" to create a fifth move.

#### 7.1.1 Incapacitation test

The lore victory window is 60 continuous seconds of ordinary encounter time. A side wins when the opponent cannot make a meaningful attempt to resist, escape back into the arena, or resume combat for that window without outside help.

- Temporary sleep, paralysis, flinching, confusion, restraint, or fear is not a win unless evidence supports the full window or the attacker can safely convert it into qualifying incapacitation.
- Unconsciousness, petrification, sealing, mind control, or compelled surrender is a win when the target cannot independently break it inside the window.
- Battlefield removal is a win when the target cannot return inside the window. Voluntary permanent flight or refusal to reengage is also a loss.
- An illusion or sensory trick alone is not a win while the target remains capable of resistance.
- Regeneration prevents a win only if it restores meaningful combat ability inside the window.
- If duration evidence cannot distinguish temporary control from qualifying incapacitation, the outcome remains unresolved.

### 7.2 Evidence identity and strength

Evidence is not combined into an unrestricted maximum-feat composite. Every evidence record has a specific `source_work_id`, `continuity_id`, episode/chapter/game/version identity where available, source kind, publication date, and direct URL or stable citation.

Core games, individual animation series, movies, limited animation, side games, manga series, TCG material, and promotional works are discovery categories, not shared continuity lanes. Claims aggregate only inside the same continuity ID. Cross-work evidence may corroborate a non-conflicting species-typical trait, but that merge is explicit and never imports incompatible scaling, exceptional individuals, or cosmology. TCG card mechanics and artwork are non-literal for physical combat unless an independent narrative source directly demonstrates the same capability.

Within one continuity, evidence is weighted in this order:

1. Repeated, serious, directly observed species-typical feats.
2. A direct feat by an ordinary wild specimen.
3. Official move, Ability, anatomy, behavior, and form descriptions.
4. Multiple consistent Pokédex statements.
5. A feat by an exceptionally trained or uniquely empowered specimen, used as an upper bound.
6. A single statement, myth, legend, gag, or promotional claim.

Each quantitative or ordinal trait stores conservative, central, and generous values. The conservative value includes repeated serious anti-feats and the lowest repeatedly supported performance. The central value uses the modal repeated serious evidence plus compatible official descriptions. The generous value may include a consistent exceptional specimen or mythic claim only as an upper bound; a gag, promotional claim, or contradicted statement cannot raise the central value. A later statement supersedes an earlier one only when the same continuity identifies it as a retcon or corrected measurement. Otherwise both remain and lower confidence.

Game lore primarily defines anatomy, innate powers, forms, and Ability rules. Animation primarily demonstrates movement, attack execution, tactics, temperament, and practical limitations. A material continuity disagreement is labeled `continuity-dependent` and produces separate lane outcomes before any report summary.

The single primary lore leaderboard uses the frozen `core_game_species` lane: core-game/Pokédex central traits plus only non-conflicting species-typical tactics corroborated by at least two ordinary animation depictions. A materially different animation, movie, manga, or side-game continuity produces a separate sensitivity outcome and never silently changes the primary league score. This preserves anime fighting style where it is continuity-robust while giving every ranked pair one reproducible central lane. The report highlights alternate-continuity reversals instead of averaging incompatible worlds.

Myth wording such as "said to" is evidence, not automatic literal combat capability. Creation roles, extreme temperature claims, and reality-warping descriptions require demonstrated activation, targeting, range, duration, resistance interaction, and cost before they become direct combat feats. Real-world physics fills a gap only when canon is silent and the inference does not contradict repeated depictions.

### 7.3 Combat dossier and eligibility

Every entrant receives sourced or explicitly inferred conservative, central, and generous fields for:

- form and transformation conditions;
- population status by continuity;
- official height and weight;
- ground, flight, swimming, burrowing, phasing, or teleportation movement;
- senses, detection, stealth, and effective range;
- physical and elemental offense;
- durability, barriers, regeneration, and explicit immunities;
- reaction speed, attack startup, combat movement, and travel speed as separate concepts;
- stamina and form duration;
- general intelligence, combat judgment, self-control, and temperament;
- preferred opening, fighting sequence, and distance;
- status, battlefield control, copying, mind effects, time/space effects, and unusual win conditions;
- primary and alternate four-move loadouts;
- fixed `home_arena_id` and its source;
- evidence source IDs and strength; and
- unresolved assumptions.

Unknown values remain unknown. Camera perspective is not used as measurement, travel speed is not silently converted into reaction speed, and type advantage is a strong prior rather than an automatic win.

Lore championship eligibility requires supported central values for identity/type, at least one usable offense, durability or a documented vulnerability profile, locomotion, combat reactions or typical behavior, a form/Ability profile, and habitat. It also requires at least two independent official evidence records, one of which must directly describe or demonstrate a combat-relevant trait. An entrant that fails this gate remains in the manifest with `lore_evidence_status = insufficient`; its pair rows are `unavailable`, not draws, and it is excluded from lore and consensus rankings. This rule is expected to keep Browt, Pombon, and Gecqua in the provisional appendix until more evidence is released.

Confidence grades are reproducible:

- **A:** at least two consistent direct species-typical feats, or an explicit official mechanic/Ability rule with repeated supporting depiction, and no material conflict.
- **B:** one direct ordinary-specimen feat plus at least two compatible official descriptions, or several mutually consistent official descriptions with no major anti-feat.
- **C:** primarily official descriptions or bounded physical inference, a single direct feat, or a minor continuity conflict.
- **D:** a single ambiguous statement, myth/gag dependence, major contradiction, or a dossier barely above the eligibility gate.

Core-game type immunity is a presumptive hard rule in the game-lore continuity. An explicit move or Ability bypass takes precedence. Anatomical intangibility or a separately described immunity applies beyond type only to demonstrated mechanisms. Repeated serious animation evidence may soften a type immunity inside that animation continuity; one-off exceptions affect only the generous bound. Indirect hazards bypass an immunity only when the target is independently shown vulnerable to that hazard.

Lore form duration is sourced per continuity as conservative, central, and generous time. Game turn limits apply only to the mechanics track. If animation or lore gives no duration, the conservative case lasts one ordinary attack exchange, the central case lasts the 60-second adjudication window, and the generous case lasts the full encounter; the resulting uncertainty lowers confidence and may trigger review.

### 7.4 Arenas

Every entrant has one fixed sourced or explicitly inferred home arena from this frozen taxonomy: `temperate_open`, `forest`, `mountain_cave`, `desert`, `tundra`, `freshwater_wetland`, `ocean_coast`, `volcanic`, `urban_industrial`, `sky_high_altitude`, `subterranean`, or `extradimensional`.

Each pairing is evaluated in three environments:

1. A mixed neutral arena ten kilometers in diameter with connected dry land, soil and rock, a deep-water basin with shoreline access, open air, distributed cover, moderate daylight, and ordinary weather.
2. Combatant A's fixed home arena.
3. Combatant B's fixed home arena.

Lore form activation is independent of the mechanics engine. Every selected form is active at time zero. A field-dependent form receives its sustaining weather or terrain only in its own home-arena scenario. The neutral arena keeps ordinary weather, and the opponent's home configuration takes priority in the opponent-home scenario. When conditions are absent or two requirements conflict, each form's conservative, central, and generous evidence-based duration controls reversion; there is no imported engine form-check event. A host form's required condition therefore wins in its home scenario, while neither side receives automatic weather priority in neutral ground.

The starting separation is `clamp(max(50 meters, 10 × the larger official body height or length), 50 meters, 1,000 meters)`. Both know the other's exact starting location and begin with unobstructed line of sight when their ordinary senses permit it. Cover begins at least 25 meters away, so stealth and concealment can be established after the opening rather than granted by setup.

The arena boundary is a five-kilometer radius with two kilometers of usable altitude or depth unless the sourced home is intrinsically extradimensional. Leaving the boundary invokes the 60-second return rule. Natural weather, terrain, hazards, teleportation, and environmental destruction created after the start are allowed.

Every home scenario must be jointly survivable at time zero. If the home environment would immediately kill or immobilize the visitor, that visitor starts in a connected neutral survivability pocket at the same separation. The setup does not beach an aquatic entrant or drown a terrestrial entrant by fiat. Arena record, time of day, weather, water depth, cover, and any survivability pocket are saved with the matchup.

The neutral outcome receives 50% weight and each home outcome receives 25%. A reversal by habitat is labeled `environment-dependent`, and all three arena decisions remain exposed.

### 7.5 Lore matchup process and result

The first pass applies hard interaction rules for explicit immunity, inability to target, habitat viability, form duration, phasing, regeneration, mental effects, battlefield removal, and other non-scalar counters. It then compares conservative, central, and generous offense, defense, reactions, movement, range, stamina, control, intelligence, temperament, and typical tactics.

Each arena and evidence case receives one of these exact score bands from combatant A's orientation:

- decisive A advantage: interval 0.80 to 0.95, central score 0.875;
- clear A advantage: interval 0.65 to under 0.80, central score 0.725;
- slight A advantage: interval 0.55 to under 0.65, central score 0.600;
- unresolved or proven draw: interval 0.45 to under 0.55, central score 0.500;
- slight B advantage: interval above 0.35 to 0.45, central score 0.400;
- clear B advantage: interval above 0.20 to 0.35, central score 0.275; and
- decisive B advantage: interval 0.05 to 0.20, central score 0.125.

For each conservative, central, and generous evidence case, the overall lore score is `0.50 * neutral + 0.25 * A-home + 0.25 * B-home`. Lower and upper bounds use the corresponding weighted interval endpoints. A central overall score above 0.55 is a categorical A win, below 0.45 is a categorical B win, and otherwise is unresolved/draw. The ranking uses the continuous central score; categorical wins and draws feed Copeland reporting only. B's score is exactly `1 - A's score`.

Every pair stores `outcome_status` as `win_A`, `win_B`, `proven_draw`, `unresolved`, or `unavailable`, plus all nine arena/evidence decisions, weighted lower/central/upper results, decisive interaction, environment sensitivity, evidence source IDs inherited from both dossiers, continuity-specific outcomes, unresolved assumptions, and A-through-D confidence. `proven_draw` means affirmative evidence shows neither side can satisfy the incapacitation test; `unresolved` means available evidence cannot select a result. Both have central score 0.5, but they remain distinct in confidence, Condorcet tests, and report language. Pair confidence is the worse of the two dossier grades and the interaction-rule grade after any direct review. An `unavailable` row caused by insufficient evidence has no numeric score and cannot enter ranking totals.

Close, top-ranked, counterintuitive, D-confidence, continuity-dependent, and champion-deciding lore fights receive a direct evidence review. The exhaustive dataset contains concise factor records for every pair; full prose adjudications are reserved for the reviewed subset rather than fabricating a million hand-written narratives.

## 8. Pair accounting and ranking

Each track generates pairs from its unique canonical combatant IDs, not from aliases. The game, lore, and consensus datasets therefore contain exactly one row for every unordered, non-self pair in their respective canonical universes. A row is `available` only when both canonical entrants meet that track's eligibility rules; otherwise it is retained with an explicit unavailable reason and null outcome values. The ranked available subset contains exactly `N * (N - 1) / 2` numeric rows for that track's eligible roster. Alias lookup resolves to the saved canonical row without adding a duplicate. The pair key sorts the two canonical stable IDs so A-versus-B and B-versus-A cannot become duplicate fights.

The primary per-pair score is continuous expected points: `S = P(win) + 0.5 * P(draw)` in the mechanics track and the exact weighted central score in the lore track. The primary leaderboard sorts by the sum of those pair scores. Categorical reporting separately assigns 1 for a declared win, 0.5 for a declared draw or unresolved result, and 0 for a declared loss; that discrete value feeds outright records and Copeland checks but never replaces the primary expected score.

The report also shows:

- outright win count;
- Copeland score;
- worst-matchup or maximin score;
- direct head-to-head result;
- uncertainty band; and
- whether a true Condorcet winner exists.

A true Condorcet winner must have a declared categorical win over every other eligible canonical entrant. A proven draw prevents Condorcet status, while any unresolved or unavailable head-to-head means the analysis cannot assert Condorcet status and instead labels the entrant a possible candidate pending evidence.

Separate leaderboards identify:

1. Player-legal game champion from a separate round robin containing only contestants with `official_player_controllable = true` and `mechanics_eligible = true`.
2. Unrestricted game champion, including official boss-only forms.
3. Lore/anime champion.
4. Combined consensus leader.

The unrestricted game leaderboard is a separate round robin over every `mechanics_eligible` contestant, including the explicit boss allowlist. Player-legal entrants are not ranked against boss-only opponents for the player-legal champion.

The consensus is an interpretation layer, not a third canon. For every pair eligible in both tracks, it averages the game expected score and lore weighted central score at equal 50% weight, then computes the same round-robin ranking. Mechanics-ineligible and lore-insufficient provisional species are excluded rather than scored as draws. If the two primary tracks disagree, the report leads with both champions and labels the consensus leader rather than calling it objectively universal.

## 9. Evolution-family coverage

Every combatant maps to an evolution family and stage. The evolution output includes every internal unique pair in that family, including branched and regional evolutions.

For example, the Bulbasaur family contains:

- Bulbasaur versus Ivysaur;
- Bulbasaur versus Venusaur; and
- Ivysaur versus Venusaur.

Each family table shows the game result, lore result, consensus result when eligible, decisive factors, and each stage's full-league record. Evolution stage itself never contributes a bonus.

## 10. Data and component boundaries

The implementation is divided into independently testable units:

1. **Source snapshotter** — pins official and simulator data identities, retrieval dates, hashes, and coverage gaps.
2. **Roster builder** — converts raw species/form data plus explicit inclusion rules into the canonical manifest and exclusion table.
3. **Evolution mapper** — assigns family, branches, and stage metadata without changing combat identity.
4. **Game profile builder** — creates stats, typing, Ability, learnset, form, legality, and candidate-build records.
5. **Game analytical engine** — scores every pair and selects escalation candidates.
6. **Battle simulator adapter** — validates builds, runs pinned seeds, stores results, and checks seat symmetry.
7. **Game build optimizer** — performs candidate pruning and double-oracle refinement for escalated fights.
8. **Lore dossier builder** — stores sourced traits, evidence bands, fighting-style fields, and explicit inferences.
9. **Lore matchup engine** — evaluates hard interactions, arenas, evidence bands, and escalation candidates.
10. **Ranking engine** — produces track-specific and consensus leaderboards plus Condorcet and maximin checks.
11. **Evolution reporter** — generates every family's internal matchup table.
12. **Lookup tool** — returns both orientations of a requested pair from the canonical unordered record.
13. **Report packager** — builds one portable HTML report through the canonical analytics artifact renderer and links the supporting files.

Each derived record retains source IDs, model version, ruleset version, and method label so analytical, simulated, and manually reviewed outcomes are distinguishable.

## 11. Deliverables

User-facing files are written under `outputs/`:

- `all-pokemon-battle-league-report.html` — primary portable report.
- `combatants.parquet` and `combatants.csv` — canonical roster and form manifest.
- `excluded-forms.csv` — explicit exclusion audit.
- `game-builds.parquet` — legal candidate and selected builds.
- `game-matchups.parquet` and `game-matchups.csv.gz` — complete game results.
- `lore-dossiers.parquet` — structured evidence and fighting-style profiles.
- `lore-matchups.parquet` and `lore-matchups.csv.gz` — complete lore results.
- `combined-matchups.parquet` and `combined-matchups.csv.gz` — pair-level consensus results.
- `rankings.csv` — all leaderboards and uncertainty fields.
- `evolution-family-matchups.csv` — every within-family comparison.
- `run-manifest.json` — rules, source versions, hashes, seeds, thresholds, counts, and limitations.
- `lookup_matchup.py` — local pair-query utility with exact-name and stable-ID support.

Intermediate caches, source extracts, test fixtures, and logs remain under `work/` and are not presented as final deliverables.

## 12. Report structure

The primary report uses the executive report shape for a Pokémon-savvy general reader:

1. Short plain-English title.
2. Visible `Executive Summary` immediately answering who wins each track.
3. Key findings with visual evidence:
   - track champions and top contenders;
   - game-versus-lore agreement and disagreement;
   - decisive finalist matchups and nontransitive cycles;
   - unrestricted boss impact;
   - evolution-family patterns and selected examples; and
   - uncertainty and sensitivity that could change the conclusion.
4. How to inspect any pairing and use the supporting datasets.
5. Further questions or results that remain unresolved.
6. Caveats and assumptions.

Planned visuals are limited to questions that benefit from them: track leaderboards, a game-versus-lore rank comparison, a top-contender matchup matrix, and an evolution-stage comparison if the data supports a readable view. Every chart receives adjacent interpretation and canonical source metadata. Full million-scale detail remains in Parquet and compressed CSV rather than being embedded into an unreadable browser table.

The HTML report is authored as a validated analytics artifact and packaged once through the shared portable report renderer. It preserves light/dark system appearance, semantic fallbacks, and source affordances. Supporting data files are evidence artifacts, not parallel report surfaces.

## 13. Validation and quality gates

### 13.1 Roster

- The released numbered-species assertion is exactly 1,025 at the cutoff.
- The provisional unnumbered-species assertion is exactly three: Browt, Pombon, and Gecqua.
- Every released National Pokédex species appears at least once.
- Every included battle-distinct form has a unique stable ID and rationale.
- Every reviewed cosmetic or excluded modifier has an exclusion reason.
- No duplicate aliases survive as contestants.
- Game and lore equivalence groups preserve real differences and collapse only track-identical aliases.
- Provisional, realtime-only, incomplete-profile, historical, and boss-only entries have correct eligibility and player-controllability flags.

### 13.2 Pair coverage

- No self-pairs.
- No duplicate unordered pairs.
- Each full track dataset's row count equals `M_track * (M_track - 1) / 2` for that track's unique canonical-universe size, including unavailable rows.
- Each track's available numeric row count equals `N * (N - 1) / 2` for that track's eligible size `N`.
- Mirrored lookup returns complementary scores from the same canonical row.
- Every alias resolves to exactly one canonical result without changing canonical pair or ranking counts.
- Numeric win, loss, and draw probabilities sum to one within tolerance for analytical and simulated mechanics rows; unavailable lore rows have all numeric outcome fields null.

### 13.3 Mechanics

- Ordinary generated builds pass the pinned team validator; Eternamax passes the dedicated exact encounter-profile validator and never borrows base-form legality.
- Type immunity, Ability bypass, priority, speed-tie, fixed-damage, simultaneous-KO, form-duration, and 200-turn loop fixtures pass.
- Generic Tera, Z-Moves, Dynamax, ordinary items, switching, and teammates cannot leak into the format; the named Ogerpon/Terapagos and Gigantamax exceptions match their explicit fixtures.
- Level-100 formulas, required-item interactions, Dynamax Level 0 HP scaling, three-turn Gigantamax reversion, field conflicts, and battle-state reversion checks match the pinned override table.
- The controller cannot access future RNG and produces identical choices from identical state, build, controller version, and seed.
- Surrogate training has exactly 10,000 stratified pairs, a frozen 80/20 split, calibrated probability totals, and saved 90% conformal diagnostics.
- Identical source snapshot, build IDs, and seed schedule reproduce identical simulations.
- Seat-order review begins only after at least 256 seed pairs, each containing one battle in each position. A paired permutation test at two-sided alpha 0.01 plus an absolute expected-score difference above five percentage points triggers review; the raw difference remains reported at every sample size.

### 13.4 Lore

- Every nontrivial dossier claim has a source ID or an explicit inference flag.
- Every evidence record has a specific work and continuity ID; no incompatible continuity feats or TCG mechanics are silently combined.
- Primary and alternate move loadouts satisfy the four-move policy, and deliberate offensive feats cannot bypass it as unlabeled innate powers.
- The 60-second incapacitation, return, regeneration, surrender, sealing, mind-control, and temporary-status fixtures pass.
- Lore eligibility applies the dossier-completeness gate; insufficient records are unavailable and excluded from rankings.
- Home-environment weights are exactly 25%, neutral is exactly 50%, and all three outcomes remain available.
- Starting distance, line of sight, boundary, jointly survivable pocket, and fixed home-arena selection are reproducible from saved fields.
- Explicit immunity, bypass, intangibility, indirect-hazard, and inability-to-target rules have fixtures.
- Conservative, central, and generous trait and matchup values obey the evidence policy and weighted score mapping.
- A-through-D confidence grades match their source-count and conflict requirements.
- Myths, gags, trained-individual feats, population status, form duration, and unknown values retain their evidence labels.

### 13.5 Rankings and evolution

- Total score equals the sum of pair scores.
- Condorcet, Copeland, expected-points, and maximin calculations have small hand-computed fixtures.
- Consensus includes only pairs eligible in both tracks and uses equal track weight.
- Every multi-member evolution family has all internal combinations.
- The Bulbasaur-Ivysaur-Venusaur fixture contains exactly three internal pairs.

### 13.6 Report

- The title is short and the first visible section is `Executive Summary`.
- The answer appears before methodology.
- Every major section has a visible, story-specific heading and an explicit implication.
- Every chart or table has adjacent interpretation and source metadata.
- The packaged report's structural or browser verification receipt passes; any structural-only limitation is disclosed.
- All final file links resolve inside `outputs/`.

## 14. Known limitations

- Exhaustive pair coverage does not make optimal move selection mathematically exact. Legal build space, simultaneous decisions, randomness, and long battle trees require pruning and adaptive simulation.
- The all-era mechanics track is a documented custom composite, not an official tournament format.
- Analytical-only game results are lower-confidence than deeply simulated results; the method label and uncertainty fields preserve that distinction.
- Lore is contradictory and unevenly documented. Evidence bands and continuity separation reduce false certainty but cannot eliminate judgment.
- Broad lore results are structured matchup adjudications, not individually hand-written essays. Close and consequential fights receive deeper review.
- Browt, Pombon, and Gecqua lack complete released mechanics and therefore cannot enter the game or consensus rankings at the cutoff. They also remain outside the lore championship whenever the dossier-completeness gate returns `insufficient`.
- A combined 50/50 index is an explicitly chosen comparison tool, not a canonical law of Pokémon.
- New releases after August 14, 2026 require a new pinned run rather than silently changing this result.

## 15. Source baseline

Primary and technical sources to pin or cite include:

- Official National Pokédex: https://www.pokemon.com/us/pokedex
- Pokémon Winds and Pokémon Waves reveal: https://windswaves.pokemon.com/en-us/?pubDate=20260306
- Pokémon Champions release and current mechanics context: https://www.pokemon.com/us/pokemon-news/pokemon-champions-releases-on-nintendo-switch-and-nintendo-switch-2-on-april-8-2026
- Pokémon Legends: Z-A Mega Evolution: https://legends.pokemon.com/en-us/mega-pokemon
- Official Gigantamax explanation: https://swordshield.pokemon.com/en-us/gameplay/gigantamax/
- Pokémon Legends: Arceus species behavior and battle context: https://legends.arceus.pokemon.com/en-us/gameplay/
- Official animation catalog context: https://parents.pokemon.com/en-us/animation/
- Official Arceus description: https://legends.arceus.pokemon.com/en-us/pokemon/arceus/
- Pokémon Showdown battle-data snapshot: https://play.pokemonshowdown.com/data/
- Pokémon Showdown simulator API: https://github.com/smogon/pokemon-showdown/blob/master/sim/SIMULATOR.md
- Pokémon Showdown form model: https://github.com/smogon/pokemon-showdown/blob/master/data/FORMES.md
- Pokémon Showdown team validator API: https://github.com/smogon/pokemon-showdown/blob/master/sim/TEAMS.md
- Smogon damage calculator API: https://github.com/smogon/damage-calc/blob/master/README.md

Secondary indexes may be used to discover edge cases, but roster identity, mechanics, and major claims must resolve to pinned official or technical source records wherever available. Coverage gaps remain explicit.

## 16. Acceptance criteria

The project is complete only when:

1. The roster and exclusion manifests pass coverage checks.
2. Every eligible unique pair has a game, lore, and/or consensus record as defined.
3. Every evolution family has complete internal pair coverage.
4. All track-specific leaderboards and winner claims derive from saved canonical pair data.
5. Champion-deciding and ranking-sensitive fights receive the required escalation and review.
6. The report directly answers the user's question and distinguishes player-legal, unrestricted, lore, and consensus results.
7. Every material uncertainty, unavailable result, and custom-composite rule is disclosed.
8. The portable HTML report and listed supporting outputs pass their validation checks.

## 17. Out of scope

- Trainer skill, friendship bonuses, battle items, team synergy, switching, breeding strategy, or six-on-six competitive tiers.
- A lethal death-battle interpretation.
- Universal Tera-type, Dynamax, or Z-Move duplicates for every contestant.
- Cosmetic forms as independent fighters.
- Fabricated stats, moves, feats, or mechanics for unreleased Pokémon.
- Treating a single elimination bracket as the definitive ranking.
