"""Validated contestant-manifest records and roster conversion boundaries."""

from collections.abc import Iterable
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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

    @field_validator(
        "source_form_id",
        "base_species_id",
        "display_name",
        "source_version",
        mode="before",
    )
    @classmethod
    def normalize_required_text(cls, value: object) -> str:
        """Normalize source identity text without accepting blank values."""
        return _required_text(value)

    @field_validator("form_name", mode="before")
    @classmethod
    def normalize_form_name(cls, value: object) -> str | None:
        """Normalize a nullable form label."""
        return _optional_text(value)

    @field_validator("source_ids", mode="before")
    @classmethod
    def normalize_source_ids(cls, value: object) -> tuple[str, ...]:
        """Preserve ordered source provenance while rejecting invalid slots."""
        return _source_ids(value)


class FormDecision(BaseModel):
    """A frozen, explicit audit decision for exactly one source form."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_form_id: str = Field(min_length=1)
    inclusion_status: InclusionStatus
    reason_code: str | None = None
    reason_text: str | None = None
    activation_class: ActivationClass
    activation_rule: str
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

    @field_validator(
        "source_form_id",
        "game_equivalence_hint",
        "lore_equivalence_hint",
        mode="before",
    )
    @classmethod
    def normalize_required_text(cls, value: object) -> str:
        """Normalize required decision identifiers and equivalence hints."""
        return _required_text(value)

    @field_validator(
        "reason_code",
        "reason_text",
        "required_form_item",
        "required_form_condition",
        "inclusion_rationale",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> str | None:
        """Normalize optional decision narrative and requirement text."""
        return _optional_text(value)

    @field_validator("activation_rule", mode="before")
    @classmethod
    def normalize_activation_rule(cls, value: object) -> str:
        """Require an activation rule for every audited source form."""
        return _required_text(value)

    @field_validator("source_ids", mode="before")
    @classmethod
    def normalize_source_ids(cls, value: object) -> tuple[str, ...]:
        """Preserve ordered decision provenance while rejecting invalid slots."""
        return _source_ids(value)

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


def _required_text(value: object) -> str:
    """Trim a required text value and reject blank or non-text input."""
    if not isinstance(value, str) or not (normalized := value.strip()):
        raise ValueError("must not be blank")
    return normalized


def _optional_text(value: object) -> str | None:
    """Trim optional text, preserving absent and blank CSV cells as ``None``."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("must be text or null")
    return value.strip() or None


def _source_ids(value: object) -> tuple[str, ...]:
    """Validate ordered source IDs without silently losing empty provenance."""
    if isinstance(value, str) or not isinstance(value, Iterable):
        raise TypeError("source_ids must be an iterable of nonblank strings")
    normalized = tuple(_required_text(item) for item in value)
    if not normalized:
        raise ValueError("source_ids must not be empty")
    if len(set(normalized)) != len(normalized):
        raise ValueError("source_ids must not contain duplicates")
    return normalized


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

    @field_validator(
        "combatant_id",
        "base_species_id",
        "display_name",
        "evolution_family_id",
        "source_version",
        "ruleset_version",
        "activation_rule",
        "game_equivalence_group",
        "lore_equivalence_group",
        "game_canonical_combatant_id",
        "lore_canonical_combatant_id",
        "consensus_canonical_combatant_id",
        "inclusion_rationale",
        mode="before",
    )
    @classmethod
    def normalize_required_text(cls, value: object) -> str:
        """Normalize required manifest identifiers and rationale text."""
        return _required_text(value)

    @field_validator("form_name", "required_form_item_or_condition", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> str | None:
        """Normalize nullable manifest labels and requirements."""
        return _optional_text(value)

    @field_validator("source_ids", mode="before")
    @classmethod
    def normalize_source_ids(cls, value: object) -> tuple[str, ...]:
        """Reject empty or duplicate manifest provenance IDs."""
        return _source_ids(value)

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

    @field_validator(
        "source_form_id",
        "display_name",
        "reason_code",
        "reason_text",
        "ruleset_version",
        mode="before",
    )
    @classmethod
    def normalize_required_text(cls, value: object) -> str:
        """Normalize required exclusion audit fields."""
        return _required_text(value)

    @field_validator("source_ids", mode="before")
    @classmethod
    def normalize_source_ids(cls, value: object) -> tuple[str, ...]:
        """Reject empty or duplicate exclusion provenance IDs."""
        return _source_ids(value)


class EvolutionEdge(BaseModel):
    """One pinned, sourced directed base-species evolution relation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    predecessor_species_id: str = Field(min_length=1)
    successor_species_id: str = Field(min_length=1)
    source_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("predecessor_species_id", "successor_species_id", mode="before")
    @classmethod
    def normalize_required_text(cls, value: object) -> str:
        """Normalize base-species IDs without accepting blank identifiers."""
        return _required_text(value)

    @field_validator("source_ids", mode="before")
    @classmethod
    def normalize_source_ids(cls, value: object) -> tuple[str, ...]:
        """Require ordered, unique provenance for every pinned edge."""
        return _source_ids(value)


class RosterBuild(BaseModel):
    """The included and excluded records derived from one ruleset revision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    combatants: tuple[Combatant, ...]
    exclusions: tuple[ExcludedForm, ...]
