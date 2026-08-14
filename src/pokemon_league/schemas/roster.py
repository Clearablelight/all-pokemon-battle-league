"""Validated contestant-manifest records and roster conversion boundaries."""

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


class RawForm(BaseModel):
    """One pinned source-form row before project inclusion rules are applied.

    ``catalog_complete_at_cutoff`` is a source-snapshot assertion.  It is false
    for a partial audit fixture and true only when every supplied row belongs to
    a verified complete cutoff-oriented catalog.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_form_id: str = Field(min_length=1)
    base_species_id: str = Field(min_length=1)
    national_number: int | None = Field(default=None, ge=1)
    display_name: str = Field(min_length=1)
    form_name: str | None = None
    official_form_order: int = Field(ge=0)
    source_version: str = Field(min_length=1)
    source_ids: tuple[str, ...] = Field(min_length=1)
    catalog_complete_at_cutoff: bool = False


class FormDecision(BaseModel):
    """A frozen, explicit audit decision for exactly one source form."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_form_id: str = Field(min_length=1)
    inclusion_status: InclusionStatus
    reason_code: str | None = None
    reason_text: str | None = None
    activation_class: ActivationClass
    activation_rule: str | None = None
    required_form_item: str | None = None
    required_form_condition: str | None = None
    core_series_player_legal: bool
    official_player_controllable: bool
    historical: bool
    boss_only: bool
    provisional: bool
    game_profile_status: GameProfileStatus
    lore_evidence_status: LoreEvidenceStatus
    game_equivalence_hint: str = Field(min_length=1)
    lore_equivalence_hint: str = Field(min_length=1)
    inclusion_rationale: str | None = None
    source_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_decision_invariants(self) -> "FormDecision":
        """Require status-specific audit text and constrain boss exceptions."""
        if self.inclusion_status is InclusionStatus.INCLUDED:
            if not _nonblank(self.inclusion_rationale):
                raise ValueError("included decisions require inclusion_rationale")
            if not _nonblank(self.activation_rule):
                raise ValueError("included decisions require activation_rule")
        elif not _nonblank(self.reason_code) or not _nonblank(self.reason_text):
            raise ValueError("excluded decisions require reason_code and reason_text")
        if self.boss_only and self.source_form_id != "eternatus--eternamax":
            raise ValueError(
                f"boss-only source form is not allowlisted: {self.source_form_id}"
            )
        return self


def _nonblank(value: str | None) -> bool:
    """Return whether an optional audit string contains visible text."""
    return bool(value and value.strip())


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
