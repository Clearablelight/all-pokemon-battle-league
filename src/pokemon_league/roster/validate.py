"""Fail-closed audit boundary for a publishable contestant roster."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pokemon_league.config import RunConfig
from pokemon_league.roster.equivalence import (
    GAME_FINGERPRINT_FIELDS,
    LORE_FINGERPRINT_FIELDS,
)
from pokemon_league.roster.evolution import canonical_sort_key
from pokemon_league.schemas.common import stable_id
from pokemon_league.schemas.roster import (
    Combatant,
    ExcludedForm,
    GameProfileStatus,
    InclusionStatus,
    PopulationStatus,
    RosterBuild,
)

FINAL_EVIDENCE_CUTOFF = date(2026, 8, 14)
FINAL_NUMBERED_SPECIES_COUNT = 1025
FINAL_PROVISIONAL_SPECIES = ("Browt", "Pombon", "Gecqua")


class RosterValidationError(ValueError):
    """Stable aggregate failure raised before roster artifacts may be published."""

    def __init__(self, errors: Iterable[str]) -> None:
        self.errors = tuple(sorted(set(errors)))
        message = "; ".join(self.errors) or "unknown roster validation failure"
        super().__init__(f"roster validation failed: {message}")


class RosterAudit(BaseModel):
    """Frozen summary of the validated roster and its publication provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_version: str
    ruleset_version: str
    model_version: str
    numbered_species_count: int = Field(ge=0)
    provisional_species: tuple[str, ...]
    provisional_species_count: int = Field(ge=0)
    combatant_count: int = Field(ge=0)
    exclusion_count: int = Field(ge=0)
    game_canonical_universe_size: int = Field(ge=0)
    lore_canonical_universe_size: int = Field(ge=0)
    consensus_canonical_universe_size: int = Field(ge=0)
    duplicate_combatant_ids: tuple[str, ...] = ()
    unreviewed_source_form_ids: tuple[str, ...] = ()
    invalid_alias_groups: tuple[str, ...] = ()
    coverage_gaps: tuple[str, ...] = ()
    input_hashes: dict[str, str] = Field(default_factory=dict)
    output_hashes: dict[str, str] = Field(default_factory=dict)


def validate_roster(
    build: RosterBuild, config: RunConfig, require_cutoff_counts: bool
) -> RosterAudit:
    """Revalidate a derived build and return its deterministic publication audit."""
    errors: list[str] = []
    raw_combatants = tuple(build.combatants)
    raw_exclusions = tuple(build.exclusions)
    identifiers = [row.combatant_id for row in raw_combatants]
    duplicates = tuple(
        sorted(
            identifier
            for identifier, count in Counter(identifiers).items()
            if count > 1
        )
    )
    errors.extend(f"duplicate combatant_id: {identifier}" for identifier in duplicates)

    combatants = _revalidate_combatants(raw_combatants, errors)
    exclusions = _revalidate_exclusions(raw_exclusions, errors)
    _validate_manifest_order(combatants, exclusions, errors)
    _validate_manifest_invariants(combatants, config, errors)
    invalid_alias_groups = _validate_aliases(combatants, errors)

    numbered = {
        row.national_number for row in combatants if row.national_number is not None
    }
    provisional_rows = tuple(row for row in combatants if row.provisional)
    configured_provisionals = (
        FINAL_PROVISIONAL_SPECIES
        if require_cutoff_counts
        else tuple(config.provisional_species)
    )
    if require_cutoff_counts:
        if config.numbered_species_count != FINAL_NUMBERED_SPECIES_COUNT:
            errors.append("numbered_species_count must be exactly 1025")
        if tuple(config.provisional_species) != FINAL_PROVISIONAL_SPECIES:
            errors.append(
                "provisional_species must be exactly ('Browt', 'Pombon', 'Gecqua')"
            )
        if config.evidence_cutoff != FINAL_EVIDENCE_CUTOFF:
            errors.append("evidence_cutoff must be exactly 2026-08-14")
    if len(set(configured_provisionals)) != len(configured_provisionals):
        errors.append("RunConfig provisional_species contains duplicates")
    provisional_names = tuple(row.display_name for row in provisional_rows)
    _validate_provisionals(
        combatants,
        configured_provisionals,
        require_cutoff_counts=require_cutoff_counts,
        errors=errors,
    )
    if require_cutoff_counts:
        expected_numbers = set(range(1, FINAL_NUMBERED_SPECIES_COUNT + 1))
        if numbered != expected_numbers:
            missing = sorted(expected_numbers - numbered)
            unexpected = sorted(numbered - expected_numbers)
            errors.append(
                "numbered National set must be exactly "
                f"1..{FINAL_NUMBERED_SPECIES_COUNT} "
                f"(missing={missing}, unexpected={unexpected})"
            )

    if errors:
        raise RosterValidationError(errors)

    ordered_provisionals = tuple(
        name for name in configured_provisionals if name in provisional_names
    )
    return RosterAudit(
        project_version=config.project_version,
        ruleset_version=config.ruleset_version,
        model_version=config.model_version,
        numbered_species_count=len(numbered),
        provisional_species=ordered_provisionals,
        provisional_species_count=len(provisional_rows),
        combatant_count=len(combatants),
        exclusion_count=len(exclusions),
        game_canonical_universe_size=len(
            {row.game_canonical_combatant_id for row in combatants}
        ),
        lore_canonical_universe_size=len(
            {row.lore_canonical_combatant_id for row in combatants}
        ),
        consensus_canonical_universe_size=len(
            {row.consensus_canonical_combatant_id for row in combatants}
        ),
        duplicate_combatant_ids=duplicates,
        invalid_alias_groups=invalid_alias_groups,
    )


def _revalidate_combatants(
    rows: tuple[Combatant, ...], errors: list[str]
) -> tuple[Combatant, ...]:
    validated: list[Combatant] = []
    for index, row in enumerate(rows):
        try:
            validated.append(Combatant.model_validate(row.model_dump()))
        except ValidationError as error:
            errors.append(
                f"invalid combatant at index {index}: {_compact_validation(error)}"
            )
    return tuple(validated)


def _revalidate_exclusions(
    rows: tuple[ExcludedForm, ...], errors: list[str]
) -> tuple[ExcludedForm, ...]:
    validated: list[ExcludedForm] = []
    for index, row in enumerate(rows):
        try:
            validated.append(ExcludedForm.model_validate(row.model_dump()))
        except ValidationError as error:
            errors.append(
                f"invalid exclusion at index {index}: {_compact_validation(error)}"
            )
    identifiers = [row.source_form_id for row in validated]
    for identifier, count in sorted(Counter(identifiers).items()):
        if count > 1:
            errors.append(f"duplicate exclusion source_form_id: {identifier}")
    return tuple(validated)


def _compact_validation(error: ValidationError) -> str:
    """Render Pydantic failures without unstable URLs or pretty-print wrapping."""
    return ", ".join(
        f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
        for item in error.errors(include_url=False)
    )


def _validate_manifest_order(
    combatants: tuple[Combatant, ...],
    exclusions: tuple[ExcludedForm, ...],
    errors: list[str],
) -> None:
    if combatants != tuple(sorted(combatants, key=canonical_sort_key)):
        errors.append(
            "combatants are not deterministically sorted by National number, form order, combatant_id"
        )
    if exclusions != tuple(sorted(exclusions, key=lambda row: row.source_form_id)):
        errors.append("exclusions are not deterministically sorted by source_form_id")


def _validate_manifest_invariants(
    combatants: tuple[Combatant, ...], config: RunConfig, errors: list[str]
) -> None:
    configured = set(config.provisional_species)
    for row in combatants:
        expected_id = (
            stable_id(row.base_species_id, row.form_name)
            if row.form_name
            else stable_id(row.base_species_id)
        )
        if row.combatant_id != expected_id:
            errors.append(
                f"invalid deterministic combatant_id {row.combatant_id}: expected {expected_id}"
            )
        if row.ruleset_version != config.ruleset_version:
            errors.append(
                f"ruleset_version drift for {row.combatant_id}: {row.ruleset_version}"
            )
        if row.inclusion_status is not InclusionStatus.INCLUDED:
            errors.append(f"combatant is not included: {row.combatant_id}")
        complete = row.game_profile_status is GameProfileStatus.COMPLETE_TURN_BASED
        if row.mechanics_eligible != complete:
            errors.append(
                f"mechanics_eligible drift for {row.combatant_id}: must match complete_turn_based"
            )
        if row.official_player_controllable and not row.core_series_player_legal:
            errors.append(
                f"player legality drift for {row.combatant_id}: controllable requires core-series legality"
            )
        if row.boss_only:
            if row.combatant_id != "eternatus--eternamax":
                errors.append(
                    f"boss-only combatant is not allowlisted: {row.combatant_id}"
                )
            if row.core_series_player_legal or row.official_player_controllable:
                errors.append(
                    f"boss-only combatant must not be player-legal: {row.combatant_id}"
                )
        if row.provisional != (row.population_status is PopulationStatus.PROVISIONAL):
            errors.append(f"provisional population_status drift for {row.combatant_id}")
        if row.display_name in configured and not row.provisional:
            errors.append(
                f"configured provisional species must be provisional: {row.display_name}"
            )


def _validate_provisionals(
    combatants: tuple[Combatant, ...],
    configured: tuple[str, ...],
    *,
    require_cutoff_counts: bool,
    errors: list[str],
) -> None:
    configured_set = set(configured)
    provisional_rows = tuple(row for row in combatants if row.provisional)
    actual_names = [row.display_name for row in provisional_rows]
    for row in provisional_rows:
        if row.display_name not in configured_set:
            errors.append(f"provisional entrant is not configured: {row.display_name}")
        if row.national_number is not None:
            errors.append(f"provisional entrant must be unnumbered: {row.display_name}")
        if row.mechanics_eligible:
            errors.append(
                f"provisional entrant must be mechanics-ineligible: {row.display_name}"
            )
        if row.game_profile_status is GameProfileStatus.COMPLETE_TURN_BASED:
            errors.append(
                f"provisional entrant cannot have a complete game profile: {row.display_name}"
            )
    if require_cutoff_counts:
        actual_counts = Counter(actual_names)
        if actual_counts != Counter(configured):
            errors.append(
                "provisional entrants must be exactly RunConfig names once each "
                f"(expected={list(configured)}, actual={sorted(actual_names)})"
            )


def _validate_aliases(
    combatants: tuple[Combatant, ...], errors: list[str]
) -> tuple[str, ...]:
    if not combatants:
        return ()
    by_id = {row.combatant_id: row for row in combatants}
    invalid: list[str] = []
    _validate_track_aliases(
        combatants,
        by_id,
        track="game",
        group_field="game_equivalence_group",
        canonical_field="game_canonical_combatant_id",
        fingerprint_fields=GAME_FINGERPRINT_FIELDS,
        invalid=invalid,
        errors=errors,
    )
    _validate_track_aliases(
        combatants,
        by_id,
        track="lore",
        group_field="lore_equivalence_group",
        canonical_field="lore_canonical_combatant_id",
        fingerprint_fields=LORE_FINGERPRINT_FIELDS,
        invalid=invalid,
        errors=errors,
    )

    consensus_groups: defaultdict[tuple[str, str], list[Combatant]] = defaultdict(list)
    for row in combatants:
        consensus_groups[
            (row.game_canonical_combatant_id, row.lore_canonical_combatant_id)
        ].append(row)
    for pair, members in sorted(consensus_groups.items()):
        expected = min(members, key=canonical_sort_key).combatant_id
        actual = {row.consensus_canonical_combatant_id for row in members}
        unknown = sorted(actual - set(by_id))
        if unknown:
            errors.append(f"unknown consensus canonical reference: {unknown[0]}")
            invalid.append(f"consensus:{pair[0]}|{pair[1]}")
        if actual != {expected}:
            errors.append(
                f"invalid consensus alias group {pair!r}: expected canonical {expected}"
            )
            invalid.append(f"consensus:{pair[0]}|{pair[1]}")
    return tuple(sorted(set(invalid)))


def _validate_track_aliases(
    combatants: tuple[Combatant, ...],
    by_id: dict[str, Combatant],
    *,
    track: str,
    group_field: str,
    canonical_field: str,
    fingerprint_fields: tuple[str, ...],
    invalid: list[str],
    errors: list[str],
) -> None:
    groups: defaultdict[str, list[Combatant]] = defaultdict(list)
    for row in combatants:
        groups[str(getattr(row, group_field))].append(row)
        canonical_id = str(getattr(row, canonical_field))
        target = by_id.get(canonical_id)
        if target is None:
            errors.append(f"unknown {track} canonical reference: {canonical_id}")
            invalid.append(f"{track}:{getattr(row, group_field)}")
        elif getattr(target, group_field) != getattr(row, group_field):
            errors.append(
                f"{track} canonical reference crosses alias groups: {row.combatant_id} -> {canonical_id}"
            )
            invalid.append(f"{track}:{getattr(row, group_field)}")
    for group, members in sorted(groups.items()):
        expected = min(members, key=canonical_sort_key).combatant_id
        actual = {str(getattr(row, canonical_field)) for row in members}
        differing = sorted(
            field
            for field in fingerprint_fields
            if len({getattr(row, field) for row in members}) > 1
        )
        if actual != {expected} or differing:
            detail = f"expected canonical {expected}"
            if differing:
                detail += f", fingerprint mismatch: {', '.join(differing)}"
            errors.append(f"invalid {track} alias group {group!r}: {detail}")
            invalid.append(f"{track}:{group}")
