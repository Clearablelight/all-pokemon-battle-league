"""Deterministic, conservative game and lore alias canonicalization."""

from __future__ import annotations

from collections import defaultdict

from pokemon_league.schemas.roster import Combatant, ExcludedForm, RosterBuild

GAME_FINGERPRINT_FIELDS = (
    "game_profile_status",
    "mechanics_eligible",
    "core_series_player_legal",
    "official_player_controllable",
    "activation_class",
    "activation_rule",
    "required_form_item_or_condition",
    "boss_only",
    "historical",
)
"""Current modeled properties that must agree inside a game alias group."""

LORE_FINGERPRINT_FIELDS = (
    "lore_evidence_status",
    "population_status",
    "provisional",
    "activation_class",
    "activation_rule",
    "required_form_item_or_condition",
    "boss_only",
    "historical",
)
"""Current modeled properties that must agree inside a lore alias group."""


def canonicalize_tracks(build: RosterBuild) -> RosterBuild:
    """Choose safe per-track canonical rows and consensus aliases deterministically."""
    combatants, exclusions = _revalidate_build(build)
    _raise_for_duplicate_ids(combatants)
    game_ids = _choose_canonical_ids(
        combatants,
        group_field="game_equivalence_group",
        track="game",
        fingerprint_fields=GAME_FINGERPRINT_FIELDS,
    )
    lore_ids = _choose_canonical_ids(
        combatants,
        group_field="lore_equivalence_group",
        track="lore",
        fingerprint_fields=LORE_FINGERPRINT_FIELDS,
    )
    consensus_ids = _consensus_ids(combatants, game_ids, lore_ids)
    rows = tuple(
        row.model_copy(
            update={
                "game_canonical_combatant_id": game_ids[row.combatant_id],
                "lore_canonical_combatant_id": lore_ids[row.combatant_id],
                "consensus_canonical_combatant_id": consensus_ids[row.combatant_id],
            }
        )
        for row in sorted(combatants, key=canonical_sort_key)
    )
    return RosterBuild(combatants=rows, exclusions=exclusions)


def canonical_sort_key(combatant: Combatant) -> tuple[int, int, str]:
    """Return the frozen sort key used to choose and order canonical rows."""
    return (
        combatant.national_number if combatant.national_number is not None else 9999,
        combatant.official_form_order,
        combatant.combatant_id,
    )


def _revalidate_build(
    build: RosterBuild,
) -> tuple[tuple[Combatant, ...], tuple[ExcludedForm, ...]]:
    """Revalidate nested frozen models at the external derived-data boundary."""
    combatants = tuple(
        Combatant.model_validate(combatant.model_dump()) for combatant in build.combatants
    )
    exclusions = tuple(
        ExcludedForm.model_validate(exclusion.model_dump())
        for exclusion in build.exclusions
    )
    return combatants, exclusions


def _raise_for_duplicate_ids(combatants: tuple[Combatant, ...]) -> None:
    """Reject duplicate combatant IDs instead of allowing order-dependent grouping."""
    ids = [combatant.combatant_id for combatant in combatants]
    duplicates = sorted(combatant_id for combatant_id in set(ids) if ids.count(combatant_id) > 1)
    if duplicates:
        raise ValueError(f"duplicate combatant_id: {duplicates[0]}")


def _choose_canonical_ids(
    combatants: tuple[Combatant, ...],
    *,
    group_field: str,
    track: str,
    fingerprint_fields: tuple[str, ...],
) -> dict[str, str]:
    """Validate every alias group and map its members to one real canonical row."""
    groups: defaultdict[str, list[Combatant]] = defaultdict(list)
    for combatant in combatants:
        groups[str(getattr(combatant, group_field))].append(combatant)
    canonical_ids: dict[str, str] = {}
    for group, members in sorted(groups.items()):
        _validate_group_fingerprint(track, group, members, fingerprint_fields)
        canonical_id = min(members, key=canonical_sort_key).combatant_id
        canonical_ids.update({member.combatant_id: canonical_id for member in members})
    return canonical_ids


def _validate_group_fingerprint(
    track: str,
    group: str,
    members: list[Combatant],
    fingerprint_fields: tuple[str, ...],
) -> None:
    """Reject a shared group when any track-modeled property is not identical."""
    differing_fields = sorted(
        field
        for field in fingerprint_fields
        if len({getattr(member, field) for member in members}) > 1
    )
    if differing_fields:
        member_ids = sorted(member.combatant_id for member in members)
        raise ValueError(
            f"{track} equivalence fingerprint mismatch in group {group!r} for "
            f"members {member_ids}: {', '.join(differing_fields)}"
        )


def _consensus_ids(
    combatants: tuple[Combatant, ...],
    game_ids: dict[str, str],
    lore_ids: dict[str, str],
) -> dict[str, str]:
    """Collapse consensus only across an exact pair of track canonical IDs."""
    groups: defaultdict[tuple[str, str], list[Combatant]] = defaultdict(list)
    for combatant in combatants:
        groups[(game_ids[combatant.combatant_id], lore_ids[combatant.combatant_id])].append(
            combatant
        )
    return {
        member.combatant_id: min(members, key=canonical_sort_key).combatant_id
        for members in groups.values()
        for member in members
    }
