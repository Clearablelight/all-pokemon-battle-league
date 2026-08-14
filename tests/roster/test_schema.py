"""Contract tests for the validated contestant-manifest records."""

import pytest
from pydantic import ValidationError

from pokemon_league.schemas.roster import (
    ActivationClass,
    GameProfileStatus,
    InclusionStatus,
    LoreEvidenceStatus,
    PopulationStatus,
)
from tests.factories import combatant_factory


def test_factory_produces_complete_bulbasaur_manifest_row() -> None:
    """The shared fixture must represent a complete, playable baseline row."""
    combatant = combatant_factory()

    assert combatant.combatant_id == "bulbasaur"
    assert combatant.national_number == 1
    assert combatant.population_status is PopulationStatus.RELEASED
    assert combatant.activation_class is ActivationClass.INTRINSIC
    assert combatant.game_profile_status is GameProfileStatus.COMPLETE_TURN_BASED
    assert combatant.lore_evidence_status is LoreEvidenceStatus.LIMITED
    assert combatant.inclusion_status is InclusionStatus.INCLUDED
    assert combatant.mechanics_eligible
    assert combatant.core_series_player_legal
    assert combatant.official_player_controllable


def test_incomplete_profile_cannot_be_mechanics_eligible() -> None:
    """No missing turn-based profile may silently reach mechanics brackets."""
    with pytest.raises(ValueError, match="complete_turn_based"):
        combatant_factory(
            game_profile_status=GameProfileStatus.INCOMPLETE,
            mechanics_eligible=True,
        )


def test_complete_profile_cannot_be_mechanics_ineligible() -> None:
    """A fully profiled form must not be omitted from mechanics by stale flags."""
    with pytest.raises(ValueError, match="complete_turn_based"):
        combatant_factory(mechanics_eligible=False)


@pytest.mark.parametrize(
    ("flag", "value"),
    (("core_series_player_legal", True), ("official_player_controllable", True)),
)
def test_boss_only_combatants_are_never_player_legal(flag: str, value: bool) -> None:
    """Boss-form rows cannot leak into either player-legal leaderboard."""
    with pytest.raises(ValueError, match="boss-only"):
        combatant_factory(boss_only=True, **{flag: value})


def test_combatant_rejects_unknown_manifest_fields() -> None:
    """Unexpected source columns must not become silently accepted roster data."""
    with pytest.raises(ValidationError, match="unexpected_column"):
        combatant_factory(unexpected_column="not reviewed")
