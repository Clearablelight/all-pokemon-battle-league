"""Tests for deterministic, property-safe per-track alias canonicalization."""

from __future__ import annotations

import pytest

from pokemon_league.roster.equivalence import (
    GAME_FINGERPRINT_FIELDS,
    LORE_FINGERPRINT_FIELDS,
    canonicalize_tracks,
)
from pokemon_league.schemas.roster import ExcludedForm, RosterBuild
from tests.factories import combatant_factory


def _row(
    combatant_id: str,
    number: int | None,
    *,
    game_group: str = "game-group",
    lore_group: str = "lore-group",
    **overrides: object,
):
    return combatant_factory(
        combatant_id=combatant_id,
        base_species_id=combatant_id,
        national_number=number,
        display_name=combatant_id.title(),
        game_equivalence_group=game_group,
        lore_equivalence_group=lore_group,
        game_canonical_combatant_id=combatant_id,
        lore_canonical_combatant_id=combatant_id,
        consensus_canonical_combatant_id=combatant_id,
        **overrides,
    )


def _build(*rows, exclusions=()):
    return RosterBuild(combatants=tuple(rows), exclusions=tuple(exclusions))


def test_consensus_collapses_only_when_both_track_ids_match() -> None:
    """Sharing game canonical identity alone never collapses consensus identity."""
    build = _build(
        _row("alpha", 2, lore_group="lore-alpha"),
        _row("beta", 1, lore_group="lore-beta"),
    )

    result = canonicalize_tracks(build)
    first, second = result.combatants

    assert first.game_canonical_combatant_id == second.game_canonical_combatant_id == "beta"
    assert first.lore_canonical_combatant_id != second.lore_canonical_combatant_id
    assert first.consensus_canonical_combatant_id != second.consensus_canonical_combatant_id


def test_consensus_collapses_when_both_track_ids_match() -> None:
    """The exact pair of track canonical IDs defines a consensus alias class."""
    result = canonicalize_tracks(_build(_row("alpha", 2), _row("beta", 1)))

    assert {row.consensus_canonical_combatant_id for row in result.combatants} == {"beta"}


def test_canonicalization_uses_declared_sort_key_and_is_input_order_independent() -> None:
    """Number, form order, then ID select one actual member deterministically."""
    rows = (
        _row("zeta", None, official_form_order=0),
        _row("beta", 10, official_form_order=1),
        _row("alpha", 10, official_form_order=1),
        _row("omega", 10, official_form_order=0),
    )

    forward = canonicalize_tracks(_build(*rows))
    shuffled = canonicalize_tracks(_build(*reversed(rows)))

    assert forward == shuffled
    assert [row.combatant_id for row in forward.combatants] == [
        "omega",
        "alpha",
        "beta",
        "zeta",
    ]
    assert {row.game_canonical_combatant_id for row in forward.combatants} == {"omega"}
    assert {row.lore_canonical_combatant_id for row in forward.combatants} == {"omega"}
    member_ids = {row.combatant_id for row in forward.combatants}
    assert {row.consensus_canonical_combatant_id for row in forward.combatants} <= member_ids


def test_game_aliases_may_have_distinct_lore_properties() -> None:
    """A valid asymmetric alias is evaluated only against its shared game facts."""
    build = _build(
        _row("alpha", 1, lore_group="lore-alpha", lore_evidence_status="limited"),
        _row("beta", 2, lore_group="lore-beta", lore_evidence_status="complete"),
    )

    result = canonicalize_tracks(build)

    assert [row.game_canonical_combatant_id for row in result.combatants] == [
        "alpha",
        "alpha",
    ]
    assert [row.lore_canonical_combatant_id for row in result.combatants] == [
        "alpha",
        "beta",
    ]


def test_game_group_fingerprint_mismatch_names_track_group_members_and_fields() -> None:
    """Shared game aliases fail if any modeled game property is different."""
    build = _build(
        _row("alpha", 1, activation_rule="standard rule"),
        _row("beta", 2, activation_rule="different rule"),
    )

    with pytest.raises(
        ValueError,
        match=(
            "game equivalence fingerprint mismatch in group 'game-group' for members "
            r"\['alpha', 'beta'\]: activation_rule"
        ),
    ):
        canonicalize_tracks(build)


def test_lore_group_fingerprint_mismatch_names_track_group_members_and_fields() -> None:
    """Shared lore aliases fail if any modeled lore property is different."""
    build = _build(
        _row("alpha", 1, lore_evidence_status="limited"),
        _row("beta", 2, lore_evidence_status="complete"),
    )

    with pytest.raises(
        ValueError,
        match=(
            "lore equivalence fingerprint mismatch in group 'lore-group' for members "
            r"\['alpha', 'beta'\]: lore_evidence_status"
        ),
    ):
        canonicalize_tracks(build)


def test_fingerprint_contracts_remain_explicit_and_conservative() -> None:
    """Future aliases cannot silently omit modeled facts from either comparison."""
    assert GAME_FINGERPRINT_FIELDS == (
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
    assert LORE_FINGERPRINT_FIELDS == (
        "lore_evidence_status",
        "population_status",
        "provisional",
        "activation_class",
        "activation_rule",
        "required_form_item_or_condition",
        "boss_only",
        "historical",
    )


def test_game_group_rejects_player_legality_mismatch() -> None:
    """Game aliases may not collapse rows with different player-legal facts."""
    build = _build(
        _row("alpha", 1),
        _row("beta", 2, core_series_player_legal=False),
    )

    with pytest.raises(
        ValueError,
        match=(
            "game equivalence fingerprint mismatch in group 'game-group' for members "
            r"\['alpha', 'beta'\]: core_series_player_legal"
        ),
    ):
        canonicalize_tracks(build)


@pytest.mark.parametrize(
    ("rows", "message"),
    (
        (
            (_row("duplicate", 1), _row("duplicate", 2)),
            "duplicate combatant_id: duplicate",
        ),
        (
            (_row("blank-game", 1).model_copy(update={"game_equivalence_group": " "}),),
            "must not be blank",
        ),
        (
            (_row("blank-lore", 1).model_copy(update={"lore_equivalence_group": " "}),),
            "must not be blank",
        ),
    ),
)
def test_canonicalization_revalidates_duplicate_and_copied_invalid_rows(
    rows, message: str
) -> None:
    """The boundary rejects duplicates and model-copy bypasses before grouping."""
    with pytest.raises(ValueError, match=message):
        canonicalize_tracks(_build(*rows))


def test_canonicalization_preserves_exclusions() -> None:
    """Mapping aliases cannot drop the audit trail for excluded forms."""
    exclusion = ExcludedForm(
        source_form_id="alpha--cosmetic",
        display_name="Alpha Cosmetic",
        reason_code="cosmetic_only",
        reason_text="Not battle distinct.",
        source_ids=("fixture",),
        ruleset_version="fixture",
    )

    result = canonicalize_tracks(_build(_row("alpha", 1), exclusions=(exclusion,)))

    assert result.exclusions == (exclusion,)
