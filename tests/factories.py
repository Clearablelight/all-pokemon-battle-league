"""Test-only factories for valid, overridable manifest records."""

from typing import Any

from pokemon_league.schemas.roster import Combatant


def combatant_factory(**overrides: Any) -> Combatant:
    """Build a complete Bulbasaur row, applying overrides before validation."""
    values: dict[str, Any] = {
        "combatant_id": "bulbasaur",
        "base_species_id": "bulbasaur",
        "national_number": 1,
        "display_name": "Bulbasaur",
        "form_name": None,
        "evolution_family_id": "bulbasaur-family",
        "evolution_stage": 1,
        "population_status": "released",
        "provisional": False,
        "inclusion_status": "included",
        "source_version": "fixture",
        "source_ids": ("showdown-pokedex",),
        "ruleset_version": "fixture",
        "mechanics_eligible": True,
        "lore_evidence_status": "limited",
        "core_series_player_legal": True,
        "official_player_controllable": True,
        "activation_class": "intrinsic",
        "activation_rule": "persistent selectable identity",
        "required_form_item_or_condition": None,
        "game_profile_status": "complete_turn_based",
        "game_equivalence_group": "bulbasaur",
        "lore_equivalence_group": "bulbasaur",
        "game_canonical_combatant_id": "bulbasaur",
        "lore_canonical_combatant_id": "bulbasaur",
        "consensus_canonical_combatant_id": "bulbasaur",
        "inclusion_rationale": "Released base species with a complete turn-based profile.",
        "official_form_order": 0,
        "historical": False,
        "boss_only": False,
    }
    values.update(overrides)
    return Combatant.model_validate(values)
