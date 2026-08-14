"""Fail-closed final roster audit contracts."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from pokemon_league.config import RunConfig
from pokemon_league.roster.validate import (
    RosterAudit,
    RosterValidationError,
    validate_roster,
)
from pokemon_league.schemas.roster import RosterBuild
from tests.factories import combatant_factory


def _run_config() -> RunConfig:
    return RunConfig(
        project_version="1.0.0",
        ruleset_version="2026-08-14.1",
        model_version="2026-08-14.1",
        evidence_cutoff=date(2026, 8, 14),
        timezone="America/Chicago",
        numbered_species_count=1025,
        provisional_species=("Browt", "Pombon", "Gecqua"),
        turn_cap=200,
        seed_root=20260814,
    )


def _numbered(number: int, **overrides: object):
    combatant_id = f"species-{number:04d}"
    values: dict[str, object] = {
        "combatant_id": combatant_id,
        "base_species_id": combatant_id,
        "national_number": number,
        "display_name": f"Species {number}",
        "evolution_family_id": f"{combatant_id}-family",
        "source_ids": ("synthetic-roster",),
        "ruleset_version": "2026-08-14.1",
        "game_equivalence_group": combatant_id,
        "lore_equivalence_group": combatant_id,
        "game_canonical_combatant_id": combatant_id,
        "lore_canonical_combatant_id": combatant_id,
        "consensus_canonical_combatant_id": combatant_id,
    }
    values.update(overrides)
    return combatant_factory(**values)


def _provisional(name: str, **overrides: object):
    combatant_id = name.lower()
    values: dict[str, object] = {
        "combatant_id": combatant_id,
        "base_species_id": combatant_id,
        "national_number": None,
        "display_name": name,
        "evolution_family_id": f"{combatant_id}-family",
        "population_status": "provisional",
        "provisional": True,
        "source_ids": ("synthetic-roster",),
        "ruleset_version": "2026-08-14.1",
        "mechanics_eligible": False,
        "game_profile_status": "incomplete",
        "lore_evidence_status": "insufficient",
        "core_series_player_legal": False,
        "official_player_controllable": False,
        "game_equivalence_group": combatant_id,
        "lore_equivalence_group": combatant_id,
        "game_canonical_combatant_id": combatant_id,
        "lore_canonical_combatant_id": combatant_id,
        "consensus_canonical_combatant_id": combatant_id,
    }
    values.update(overrides)
    return combatant_factory(**values)


def _build(*rows) -> RosterBuild:
    ordered = sorted(
        rows,
        key=lambda row: (
            row.national_number if row.national_number is not None else 9999,
            row.official_form_order,
            row.combatant_id,
        ),
    )
    return RosterBuild(combatants=tuple(ordered), exclusions=())


@pytest.fixture(scope="module")
def full_roster_build() -> RosterBuild:
    return _build(
        *(_numbered(number) for number in range(1, 1026)),
        *(_provisional(name) for name in ("Browt", "Pombon", "Gecqua")),
    )


def test_cutoff_audit_requires_exact_continuous_numbered_set_and_provisionals(
    full_roster_build: RosterBuild,
) -> None:
    """A valid final audit proves exact identities, not merely matching counts."""
    audit = validate_roster(full_roster_build, _run_config(), True)

    assert audit.numbered_species_count == 1025
    assert audit.provisional_species == ("Browt", "Pombon", "Gecqua")
    assert audit.provisional_species_count == 3
    assert audit.combatant_count == 1028
    assert audit.exclusion_count == 0
    assert audit.game_canonical_universe_size == 1028
    assert audit.lore_canonical_universe_size == 1028
    assert audit.consensus_canonical_universe_size == 1028
    assert audit.duplicate_combatant_ids == ()
    assert audit.unreviewed_source_form_ids == ()
    assert audit.invalid_alias_groups == ()
    assert audit.coverage_gaps == ()


def test_cutoff_audit_rejects_gap_and_substitution_with_same_unique_count() -> None:
    """Replacing 1025 with 1026 must fail despite retaining 1,025 unique numbers."""
    build = _build(
        *(_numbered(number) for number in range(1, 1025)),
        _numbered(1026),
        *(_provisional(name) for name in ("Browt", "Pombon", "Gecqua")),
    )

    with pytest.raises(RosterValidationError, match="numbered National set"):
        validate_roster(build, _run_config(), True)


@pytest.mark.parametrize(
    ("replacement", "message"),
    (
        (_provisional("Browt", national_number=1026), "must be unnumbered"),
        (
            _provisional("Browt", provisional=False, population_status="released"),
            "exactly",
        ),
        (
            _provisional(
                "Browt",
                mechanics_eligible=True,
                game_profile_status="complete_turn_based",
            ),
            "mechanics-ineligible",
        ),
        (_provisional("Othermon"), "exactly"),
    ),
)
def test_cutoff_audit_rejects_provisional_identity_and_eligibility_drift(
    replacement, message: str
) -> None:
    """Each provisional rule is independently required by the final cutoff gate."""
    rows = [_numbered(number) for number in range(1, 1026)]
    rows.extend((_provisional("Pombon"), _provisional("Gecqua"), replacement))

    with pytest.raises(RosterValidationError, match=message):
        validate_roster(_build(*rows), _run_config(), True)


def test_audit_rejects_duplicate_combatant_ids_before_alias_resolution() -> None:
    """A duplicate manifest identity may not become order-dependent alias state."""
    duplicate = _numbered(2, combatant_id="species-0001")
    build = RosterBuild(combatants=(_numbered(1), duplicate), exclusions=())

    with pytest.raises(
        RosterValidationError, match="duplicate combatant_id: species-0001"
    ):
        validate_roster(build, _run_config(), False)


@pytest.mark.parametrize(
    ("rows", "message"),
    (
        (
            (_numbered(1, game_canonical_combatant_id="missing"),),
            "unknown game canonical reference",
        ),
        (
            (
                _numbered(1),
                _numbered(
                    2,
                    game_equivalence_group="species-0001",
                    game_canonical_combatant_id="species-0002",
                ),
            ),
            "invalid game alias group",
        ),
    ),
)
def test_audit_rejects_invalid_canonical_references_and_groups(
    rows: tuple, message: str
) -> None:
    """Canonical targets must be real, deterministic members of their alias group."""
    with pytest.raises(RosterValidationError, match=message):
        validate_roster(_build(*rows), _run_config(), False)


def test_partial_roster_validates_only_when_cutoff_counts_are_not_required() -> None:
    """Small audited fixtures remain useful but can never pass the final gate."""
    build = _build(_numbered(1))

    audit = validate_roster(build, _run_config(), False)
    assert audit.numbered_species_count == 1
    with pytest.raises(RosterValidationError, match="numbered National set"):
        validate_roster(build, _run_config(), True)


def test_audit_revalidates_copied_invalid_nested_models() -> None:
    """Pydantic model-copy bypasses cannot smuggle invalid mechanics into outputs."""
    invalid = _numbered(1).model_copy(update={"mechanics_eligible": False})
    build = _build(_numbered(1)).model_copy(update={"combatants": (invalid,)})

    with pytest.raises(RosterValidationError, match="mechanics_eligible"):
        validate_roster(build, _run_config(), False)


@pytest.mark.parametrize(
    ("row", "message"),
    (
        (
            _numbered(
                1,
                core_series_player_legal=False,
                official_player_controllable=True,
            ),
            "player legality drift",
        ),
        (
            _numbered(
                1,
                boss_only=True,
                core_series_player_legal=False,
                official_player_controllable=False,
            ),
            "boss-only combatant is not allowlisted",
        ),
        (
            _numbered(1).model_copy(update={"provisional": True}),
            "provisional population_status drift",
        ),
    ),
)
def test_audit_detects_player_boss_and_provisional_invariant_drift(
    row, message: str
) -> None:
    """Final validation repeats every cross-field invariant at the output boundary."""
    build = _build(_numbered(1)).model_copy(update={"combatants": (row,)})

    with pytest.raises(RosterValidationError, match=message):
        validate_roster(build, _run_config(), False)


def test_audit_reports_distinct_track_alias_universe_sizes() -> None:
    """Universe counts describe actual canonical IDs on every modeling track."""
    alpha = _numbered(1)
    beta = _numbered(
        2,
        game_equivalence_group="species-0001",
        game_canonical_combatant_id="species-0001",
    )

    audit = validate_roster(_build(alpha, beta), _run_config(), False)

    assert audit.game_canonical_universe_size == 1
    assert audit.lore_canonical_universe_size == 2
    assert audit.consensus_canonical_universe_size == 2


def test_roster_audit_is_frozen_and_forbids_unknown_fields(
    full_roster_build: RosterBuild,
) -> None:
    """Published audit metadata cannot silently drift after validation."""
    audit = validate_roster(full_roster_build, _run_config(), True)

    with pytest.raises(ValidationError, match="frozen"):
        audit.combatant_count = 0  # type: ignore[misc]
    with pytest.raises(ValidationError, match="unexpected"):
        RosterAudit.model_validate({**audit.model_dump(), "unexpected": True})
