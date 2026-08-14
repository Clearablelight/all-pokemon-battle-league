"""Fail-closed conversion of raw form rows and audited form decisions."""

from collections.abc import Sequence

from pokemon_league.config import RunConfig
from pokemon_league.schemas.common import stable_id
from pokemon_league.schemas.roster import (
    Combatant,
    ExcludedForm,
    FormDecision,
    InclusionStatus,
    PopulationStatus,
    RawForm,
    RosterBuild,
)


def build_roster(
    raw_forms: Sequence[RawForm],
    decisions: Sequence[FormDecision],
    config: RunConfig,
) -> RosterBuild:
    """Build a deterministically ordered roster, rejecting unreviewed scope.

    This function intentionally does not claim that a partial source input is
    comprehensive.  Every supplied raw form must have exactly one reviewed
    decision, and every decision must identify exactly one supplied raw form.
    """
    raw_forms = tuple(RawForm.model_validate(raw.model_dump()) for raw in raw_forms)
    decisions = tuple(
        FormDecision.model_validate(decision.model_dump()) for decision in decisions
    )
    raw_by_source_id = _index_unique(raw_forms, "raw")
    decision_by_source_id = _index_unique(decisions, "decision")
    missing_raw = sorted(set(decision_by_source_id) - set(raw_by_source_id))
    if missing_raw:
        raise ValueError(f"decisions reference absent source forms: {missing_raw}")

    _validate_provisionals(raw_forms, decisions, config)
    combatants: list[Combatant] = []
    combatant_ids: set[str] = set()
    exclusions: list[ExcludedForm] = []
    for raw in sorted(raw_forms, key=_raw_sort_key):
        decision = decision_by_source_id.get(raw.source_form_id)
        if decision is None:
            raise ValueError(f"unreviewed form: {raw.source_form_id}")
        _validate_decision_for_build(raw, decision)
        if decision.inclusion_status is InclusionStatus.EXCLUDED:
            exclusions.append(_excluded_from(raw, decision, config.ruleset_version))
        else:
            combatant = _combatant_from(raw, decision, config.ruleset_version)
            if combatant.combatant_id in combatant_ids:
                raise ValueError(
                    f"duplicate generated combatant_id: {combatant.combatant_id}"
                )
            combatant_ids.add(combatant.combatant_id)
            combatants.append(combatant)
    return RosterBuild(combatants=tuple(combatants), exclusions=tuple(exclusions))


def _index_unique[T: RawForm | FormDecision](
    rows: Sequence[T], kind: str
) -> dict[str, T]:
    """Index explicit source IDs while rejecting order-dependent duplicates."""
    indexed: dict[str, T] = {}
    for row in rows:
        if row.source_form_id in indexed:
            raise ValueError(f"duplicate {kind} source_form_id: {row.source_form_id}")
        indexed[row.source_form_id] = row
    return indexed


def _raw_sort_key(raw: RawForm) -> tuple[int, int, str]:
    """Return the frozen traversal key for included and excluded rows alike."""
    return (
        raw.national_number if raw.national_number is not None else 9999,
        raw.official_form_order,
        raw.source_form_id,
    )


def _validate_provisionals(
    raw_forms: Sequence[RawForm], decisions: Sequence[FormDecision], config: RunConfig
) -> None:
    """Constrain provisional flags and enforce a claimed complete catalog."""
    completeness_values = {raw.catalog_complete_at_cutoff for raw in raw_forms}
    if len(completeness_values) > 1:
        raise ValueError("mixed catalog_complete_at_cutoff flags")
    is_complete = completeness_values == {True}
    configured = set(config.provisional_species)
    if len(configured) != len(config.provisional_species):
        raise ValueError("RunConfig provisional_species must not contain duplicates")
    raw_by_source_id = {raw.source_form_id: raw for raw in raw_forms}
    provisional_counts = {name: 0 for name in configured}
    for decision in decisions:
        if not decision.provisional:
            continue
        raw = raw_by_source_id.get(decision.source_form_id)
        if raw is None:
            continue
        if raw.display_name not in configured:
            raise ValueError(f"provisional form is not configured: {raw.display_name}")
        if decision.inclusion_status is not InclusionStatus.INCLUDED:
            raise ValueError("provisional decisions must be included")
        if decision.game_profile_status.value == "complete_turn_based":
            raise ValueError("provisional decisions cannot have complete_turn_based")
        provisional_counts[raw.display_name] += 1
    if is_complete:
        missing = sorted(
            name for name, count in provisional_counts.items() if count == 0
        )
        if missing:
            raise ValueError(
                f"configured provisional names missing from complete input: {missing}"
            )
        duplicate = sorted(
            name for name, count in provisional_counts.items() if count > 1
        )
        if duplicate:
            raise ValueError(
                f"configured provisional name must appear exactly once: {duplicate[0]}"
            )


def _validate_decision_for_build(raw: RawForm, decision: FormDecision) -> None:
    """Revalidate copy-bypassed models at the conversion boundary."""
    if decision.boss_only and raw.source_form_id != "eternatus--eternamax":
        raise ValueError(
            f"boss-only source form is not allowlisted: {raw.source_form_id}"
        )
    if decision.boss_only and (
        decision.core_series_player_legal or decision.official_player_controllable
    ):
        raise ValueError("boss-only combatants must not be player-legal")
    if decision.inclusion_status is InclusionStatus.INCLUDED:
        if not _nonblank(decision.inclusion_rationale):
            raise ValueError("included decisions require inclusion_rationale")
        if not _nonblank(decision.activation_rule):
            raise ValueError("included decisions require activation_rule")
    elif not _nonblank(decision.reason_code) or not _nonblank(decision.reason_text):
        raise ValueError("excluded decisions require reason_code and reason_text")
    if decision.required_form_item and decision.required_form_condition:
        raise ValueError(
            "both required_form_item and required_form_condition are present; "
            "the current Combatant field cannot preserve both"
        )


def _combatant_from(
    raw: RawForm, decision: FormDecision, ruleset_version: str
) -> Combatant:
    """Convert one included decision with explicit Task 5 placeholder metadata."""
    combatant_id = _combatant_id(raw)
    requirement = decision.required_form_item or decision.required_form_condition
    return Combatant(
        combatant_id=combatant_id,
        base_species_id=raw.base_species_id,
        national_number=raw.national_number,
        display_name=raw.display_name,
        form_name=raw.form_name,
        evolution_family_id=f"{raw.base_species_id}-family",
        evolution_stage=1,
        population_status=(
            PopulationStatus.PROVISIONAL
            if decision.provisional
            else PopulationStatus.RELEASED
        ),
        provisional=decision.provisional,
        source_version=raw.source_version,
        source_ids=tuple(dict.fromkeys((*raw.source_ids, *decision.source_ids))),
        ruleset_version=ruleset_version,
        mechanics_eligible=(
            decision.game_profile_status.value == "complete_turn_based"
        ),
        lore_evidence_status=decision.lore_evidence_status,
        core_series_player_legal=decision.core_series_player_legal,
        official_player_controllable=decision.official_player_controllable,
        activation_class=decision.activation_class,
        activation_rule=decision.activation_rule or "",
        required_form_item_or_condition=requirement,
        game_profile_status=decision.game_profile_status,
        game_equivalence_group=decision.game_equivalence_hint,
        lore_equivalence_group=decision.lore_equivalence_hint,
        game_canonical_combatant_id=combatant_id,
        lore_canonical_combatant_id=combatant_id,
        consensus_canonical_combatant_id=combatant_id,
        inclusion_rationale=decision.inclusion_rationale or "",
        official_form_order=raw.official_form_order,
        historical=decision.historical,
        boss_only=decision.boss_only,
    )


def _excluded_from(
    raw: RawForm, decision: FormDecision, ruleset_version: str
) -> ExcludedForm:
    """Keep an excluded source identity and its audit reason in output order."""
    return ExcludedForm(
        source_form_id=raw.source_form_id,
        display_name=raw.display_name,
        reason_code=decision.reason_code or "",
        reason_text=decision.reason_text or "",
        source_ids=tuple(dict.fromkeys((*raw.source_ids, *decision.source_ids))),
        ruleset_version=ruleset_version,
    )


def _combatant_id(raw: RawForm) -> str:
    """Build the public stable ID from base identity and an optional form name."""
    return (
        stable_id(raw.base_species_id, raw.form_name)
        if raw.form_name
        else stable_id(raw.base_species_id)
    )


def _nonblank(value: str | None) -> bool:
    """Return whether an optional audit string contains visible text."""
    return bool(value and value.strip())
