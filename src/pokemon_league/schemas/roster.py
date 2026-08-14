"""Validated contestant-manifest records and roster containers."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActivationClass(str, Enum):
    """How a selected contestant form is active at battle start."""

    INTRINSIC = "intrinsic"
    TRANSFORMATION = "transformation"
    FIELD_DEPENDENT = "field_dependent"
    BATTLE_STATE = "battle_state"


class GameProfileStatus(str, Enum):
    """Completeness of a form's official turn-based combat profile."""

    COMPLETE_TURN_BASED = "complete_turn_based"
    REALTIME_ONLY = "realtime_only"
    INCOMPLETE = "incomplete"
    NOT_APPLICABLE = "not_applicable"


class LoreEvidenceStatus(str, Enum):
    """Completeness of the sourced lore dossier for a combatant."""

    COMPLETE = "complete"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


class PopulationStatus(str, Enum):
    """Whether a named species was released at the evidence cutoff."""

    RELEASED = "released"
    PROVISIONAL = "provisional"


class InclusionStatus(str, Enum):
    """Whether a reviewed source form is a separate contestant."""

    INCLUDED = "included"
    EXCLUDED = "excluded"


class Combatant(BaseModel):
    """One validated row in the canonical contestant manifest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    combatant_id: str
    base_species_id: str
    national_number: int | None = Field(default=None, ge=1)
    display_name: str
    form_name: str | None = None
    evolution_family_id: str
    evolution_stage: int = Field(ge=1)
    population_status: PopulationStatus
    provisional: bool
    inclusion_status: InclusionStatus = InclusionStatus.INCLUDED
    source_version: str
    source_ids: tuple[str, ...]
    ruleset_version: str
    mechanics_eligible: bool
    lore_evidence_status: LoreEvidenceStatus
    core_series_player_legal: bool
    official_player_controllable: bool
    activation_class: ActivationClass
    activation_rule: str
    required_form_item_or_condition: str | None = None
    game_profile_status: GameProfileStatus
    game_equivalence_group: str
    lore_equivalence_group: str
    game_canonical_combatant_id: str
    lore_canonical_combatant_id: str
    consensus_canonical_combatant_id: str
    inclusion_rationale: str
    official_form_order: int = Field(ge=0)
    historical: bool
    boss_only: bool

    @model_validator(mode="after")
    def validate_manifest_invariants(self) -> "Combatant":
        """Enforce bracket eligibility and player-legality guardrails."""
        has_complete_profile = (
            self.game_profile_status is GameProfileStatus.COMPLETE_TURN_BASED
        )
        if self.mechanics_eligible != has_complete_profile:
            raise ValueError(
                "mechanics_eligible must be true iff game_profile_status is "
                "complete_turn_based"
            )
        if self.boss_only and (
            self.core_series_player_legal or self.official_player_controllable
        ):
            raise ValueError("boss-only combatants must not be player-legal")
        return self


class ExcludedForm(BaseModel):
    """A reviewed non-contestant source form retained for auditability."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_form_id: str
    display_name: str
    reason_code: str
    reason_text: str
    source_ids: tuple[str, ...]
    ruleset_version: str


class RosterBuild(BaseModel):
    """The included and excluded records derived from one ruleset revision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    combatants: tuple[Combatant, ...]
    exclusions: tuple[ExcludedForm, ...]
