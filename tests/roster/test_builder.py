"""Tests for the fail-closed conversion of audited form decisions into a roster."""

import csv
import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from pydantic import ValidationError

from pokemon_league.config import RunConfig, load_run_config
from pokemon_league.roster.builder import build_roster
from pokemon_league.schemas import FormDecision, RawForm
from pokemon_league.schemas.roster import GameProfileStatus

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "roster"


def load_raw_forms(path: Path = FIXTURE_DIR / "raw-forms.json") -> tuple[RawForm, ...]:
    """Load the deliberately small, audited input fixture."""
    with path.open(encoding="utf-8") as handle:
        return tuple(RawForm.model_validate(row) for row in json.load(handle))


def load_form_decisions(
    path: Path = FIXTURE_DIR / "decisions.csv",
) -> tuple[FormDecision, ...]:
    """Load decisions while decoding the CSV's explicit source-ID list."""
    with path.open(newline="", encoding="utf-8") as handle:
        return tuple(
            FormDecision.model_validate(
                {
                    **row,
                    "source_ids": tuple(filter(None, row.pop("source_ids").split("|"))),
                }
            )
            for row in csv.DictReader(handle)
        )


@pytest.fixture
def raw_forms() -> tuple[RawForm, ...]:
    return load_raw_forms()


@pytest.fixture
def form_decisions() -> tuple[FormDecision, ...]:
    return load_form_decisions()


@pytest.fixture
def run_config() -> RunConfig:
    return load_run_config(Path(__file__).parents[1] / "fixtures" / "run.toml")


def test_builder_keeps_battle_forms_and_audits_cosmetics(
    raw_forms: Sequence[RawForm],
    form_decisions: Sequence[FormDecision],
    run_config: RunConfig,
) -> None:
    """Battle-distinct forms remain contestants while shiny coloration is auditable."""
    result = build_roster(raw_forms, form_decisions, run_config)

    names = {row.display_name for row in result.combatants}
    assert {
        "Venusaur",
        "Mega Venusaur",
        "Gigantamax Venusaur",
        "Eternamax Eternatus",
    } <= names
    assert "Venusaur Shiny" not in names
    assert any(
        row.display_name == "Venusaur Shiny" and row.reason_code == "cosmetic_only"
        for row in result.exclusions
    )
    eternamax = next(
        row for row in result.combatants if row.display_name == "Eternamax Eternatus"
    )
    assert eternamax.boss_only
    assert not eternamax.core_series_player_legal
    assert not eternamax.official_player_controllable


def test_builder_preserves_distinct_required_item_and_condition(
    raw_forms: Sequence[RawForm],
    form_decisions: Sequence[FormDecision],
    run_config: RunConfig,
) -> None:
    """A single requirement maps deterministically into the legacy combined field."""
    result = build_roster(raw_forms, form_decisions, run_config)

    mega = next(row for row in result.combatants if row.display_name == "Mega Venusaur")
    gmax = next(
        row for row in result.combatants if row.display_name == "Gigantamax Venusaur"
    )
    assert mega.required_form_item_or_condition == "Venusaurite"
    assert gmax.required_form_item_or_condition == "Gigantamax Factor"


def test_builder_rejects_simultaneous_item_and_condition(
    raw_forms: tuple[RawForm, ...],
    form_decisions: tuple[FormDecision, ...],
    run_config: RunConfig,
) -> None:
    """The legacy manifest column may not erase one of two independent inputs."""
    decision = form_decisions[1].model_copy(
        update={"required_form_condition": "sunlight"}
    )

    with pytest.raises(
        ValueError, match="both required_form_item and required_form_condition"
    ):
        build_roster(
            raw_forms, (form_decisions[0], decision, *form_decisions[2:]), run_config
        )


def test_provisional_species_are_present_but_not_mechanics_eligible(
    raw_forms: Sequence[RawForm],
    form_decisions: Sequence[FormDecision],
    run_config: RunConfig,
) -> None:
    """The frozen provisional trio is represented without invented game profiles."""
    result = build_roster(raw_forms, form_decisions, run_config)

    for name in ("Browt", "Pombon", "Gecqua"):
        row = next(item for item in result.combatants if item.display_name == name)
        assert row.provisional
        assert not row.mechanics_eligible
        assert row.game_profile_status is GameProfileStatus.INCOMPLETE


def test_builder_rejects_unreviewed_raw_form(
    raw_forms: tuple[RawForm, ...],
    form_decisions: tuple[FormDecision, ...],
    run_config: RunConfig,
) -> None:
    """A source addition cannot silently change the manifest scope."""
    raw = raw_forms[0].model_copy(update={"source_form_id": "venusaur--test"})

    with pytest.raises(ValueError, match="unreviewed form: venusaur--test"):
        build_roster((*raw_forms, raw), form_decisions, run_config)


def test_builder_rejects_decision_for_absent_raw_form(
    raw_forms: tuple[RawForm, ...],
    form_decisions: tuple[FormDecision, ...],
    run_config: RunConfig,
) -> None:
    """A decision cannot claim review of a form outside the source input."""
    missing = form_decisions[0].model_copy(update={"source_form_id": "absent--form"})

    with pytest.raises(ValueError, match="decisions reference absent source forms"):
        build_roster(raw_forms, (*form_decisions, missing), run_config)


def test_builder_rejects_duplicate_raw_ids(
    raw_forms: tuple[RawForm, ...],
    form_decisions: tuple[FormDecision, ...],
    run_config: RunConfig,
) -> None:
    """Duplicate raw identities are invalid rather than order-dependent."""
    with pytest.raises(ValueError, match="duplicate raw source_form_id: venusaur"):
        build_roster((*raw_forms, raw_forms[0]), form_decisions, run_config)


def test_builder_rejects_duplicate_decision_ids(
    raw_forms: tuple[RawForm, ...],
    form_decisions: tuple[FormDecision, ...],
    run_config: RunConfig,
) -> None:
    """Duplicate decisions are invalid rather than last-write-wins."""
    with pytest.raises(ValueError, match="duplicate decision source_form_id: venusaur"):
        build_roster(raw_forms, (*form_decisions, form_decisions[0]), run_config)


def test_builder_rejects_non_allowlisted_boss_form(
    raw_forms: tuple[RawForm, ...],
    form_decisions: tuple[FormDecision, ...],
    run_config: RunConfig,
) -> None:
    """The boss exception is constrained to the named Eternamax identity."""
    decision = form_decisions[0].model_copy(update={"boss_only": True})

    with pytest.raises(
        ValueError, match="boss-only source form is not allowlisted: venusaur"
    ):
        build_roster(raw_forms, (decision, *form_decisions[1:]), run_config)


@pytest.mark.parametrize(
    "legality_field",
    ("core_series_player_legal", "official_player_controllable"),
)
def test_builder_rejects_player_legal_boss_flags(
    raw_forms: tuple[RawForm, ...],
    form_decisions: tuple[FormDecision, ...],
    run_config: RunConfig,
    legality_field: str,
) -> None:
    """Boss-only forms cannot leak into either player-legal bracket."""
    boss_index = next(
        index
        for index, decision in enumerate(form_decisions)
        if decision.source_form_id == "eternatus--eternamax"
    )
    decision = form_decisions[boss_index].model_copy(update={legality_field: True})
    amended = list(form_decisions)
    amended[boss_index] = decision

    with pytest.raises(
        ValueError, match="boss-only combatants must not be player-legal"
    ):
        build_roster(raw_forms, amended, run_config)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    (
        ("inclusion_rationale", "", "included decisions require inclusion_rationale"),
        ("activation_rule", "", "included decisions require activation_rule"),
        ("reason_code", "", "excluded decisions require reason_code and reason_text"),
        ("reason_text", "", "excluded decisions require reason_code and reason_text"),
    ),
)
def test_builder_rejects_missing_status_specific_rationale_fields(
    raw_forms: tuple[RawForm, ...],
    form_decisions: tuple[FormDecision, ...],
    run_config: RunConfig,
    field: str,
    value: str,
    match: str,
) -> None:
    """Decision narratives are mandatory for the branch where they are meaningful."""
    source_id = "venusaur--shiny" if field.startswith("reason") else "venusaur"
    index = next(
        index
        for index, decision in enumerate(form_decisions)
        if decision.source_form_id == source_id
    )
    amended = list(form_decisions)
    amended[index] = amended[index].model_copy(update={field: value})

    with pytest.raises(ValueError, match=match):
        build_roster(raw_forms, amended, run_config)


def test_builder_is_independent_of_raw_and_decision_input_order(
    raw_forms: tuple[RawForm, ...],
    form_decisions: tuple[FormDecision, ...],
    run_config: RunConfig,
) -> None:
    """Stable sort keys make derived roster ordering independent of input order."""
    forward = build_roster(raw_forms, form_decisions, run_config)
    reversed_input = build_roster(
        tuple(reversed(raw_forms)), tuple(reversed(form_decisions)), run_config
    )

    assert forward == reversed_input


def test_builder_rejects_provisional_flag_outside_config(
    raw_forms: tuple[RawForm, ...],
    form_decisions: tuple[FormDecision, ...],
    run_config: RunConfig,
) -> None:
    """Only the frozen config names may be tagged as provisional."""
    decision = form_decisions[0].model_copy(update={"provisional": True})

    with pytest.raises(
        ValueError, match="provisional form is not configured: Venusaur"
    ):
        build_roster(raw_forms, (decision, *form_decisions[1:]), run_config)


def test_complete_cutoff_input_requires_every_configured_provisional_name(
    raw_forms: tuple[RawForm, ...],
    form_decisions: tuple[FormDecision, ...],
    run_config: RunConfig,
) -> None:
    """A claimed complete cutoff input cannot omit a frozen provisional entry."""
    complete_raw = tuple(
        raw.model_copy(update={"catalog_complete_at_cutoff": True}) for raw in raw_forms
    )
    incomplete_config = run_config.model_copy(
        update={"provisional_species": (*run_config.provisional_species, "Missingmon")}
    )

    with pytest.raises(
        ValueError,
        match=r"configured provisional names missing from complete input: \['Missingmon'\]",
    ):
        build_roster(complete_raw, form_decisions, incomplete_config)


def test_form_decision_is_frozen_and_forbids_unknown_fields() -> None:
    """The audit boundary cannot be mutated or accept an unreviewed CSV column."""
    decision = load_form_decisions()[0]

    with pytest.raises(ValidationError, match="frozen_instance"):
        decision.source_form_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="extra_forbidden"):
        FormDecision.model_validate({**decision.model_dump(), "unknown": "value"})


def test_decision_requires_boss_allowlist_at_model_boundary() -> None:
    """An invalid boss designation fails before it can reach conversion logic."""
    decision = load_form_decisions()[0]

    with pytest.raises(ValueError, match="boss-only source form is not allowlisted"):
        FormDecision.model_validate({**decision.model_dump(), "boss_only": True})


def test_raw_form_is_frozen_and_forbids_unknown_fields() -> None:
    """Raw source records are typed immutable inputs rather than loose dictionaries."""
    raw = load_raw_forms()[0]

    with pytest.raises(ValidationError, match="frozen_instance"):
        raw.display_name = "Changed"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="extra_forbidden"):
        RawForm.model_validate({**raw.model_dump(), "unknown": "value"})


def test_starter_config_catalog_is_schema_valid() -> None:
    """The checked-in starter catalog is explicit data, not a coverage assertion."""
    path = Path(__file__).parents[2] / "config" / "roster-decisions.csv"
    decisions = load_form_decisions(path)

    assert {row.source_form_id for row in decisions} == {
        "venusaur",
        "venusaur--mega",
        "venusaur--gigantamax",
        "venusaur--shiny",
        "eternatus--eternamax",
        "browt",
        "pombon",
        "gecqua",
    }
