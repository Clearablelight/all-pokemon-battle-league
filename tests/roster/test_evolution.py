"""Tests for deterministic, fail-closed evolution-family mapping."""

from __future__ import annotations

import itertools

import pytest
from pydantic import ValidationError

from pokemon_league.roster.evolution import assign_evolution_metadata
from pokemon_league.schemas.roster import EvolutionEdge, ExcludedForm, RosterBuild
from tests.factories import combatant_factory


def _row(
    species_id: str,
    number: int,
    name: str | None = None,
    **overrides: object,
):
    form_name = overrides.get("form_name")
    return combatant_factory(
        combatant_id=(
            species_id if form_name is None else f"{species_id}--{str(form_name).lower()}"
        ),
        base_species_id=species_id,
        national_number=number,
        display_name=name or species_id.title(),
        evolution_family_id=f"{species_id}-family",
        **overrides,
    )


def _build(*rows):
    return RosterBuild(combatants=tuple(rows), exclusions=())


def _edge(predecessor: str, successor: str, *source_ids: str) -> EvolutionEdge:
    return EvolutionEdge(
        predecessor_species_id=predecessor,
        successor_species_id=successor,
        source_ids=source_ids or ("fixture",),
    )


def test_evolution_edge_normalizes_identifiers_and_provenance() -> None:
    """Pinned edges trim fields and reject blank or duplicate provenance."""
    edge = _edge(" bulbasaur ", " ivysaur ", " source-a ", "source-b")

    assert edge.predecessor_species_id == "bulbasaur"
    assert edge.successor_species_id == "ivysaur"
    assert edge.source_ids == ("source-a", "source-b")
    with pytest.raises(ValidationError, match="must not be blank"):
        _edge("bulbasaur", "ivysaur", " ")
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        _edge("bulbasaur", "ivysaur", "source-a", "source-a")


def test_bulbasaur_family_has_three_internal_pairs() -> None:
    """A linear family receives stable family metadata for all three stages."""
    build = _build(
        _row("bulbasaur", 1, "Bulbasaur"),
        _row("ivysaur", 2, "Ivysaur"),
        _row("venusaur", 3, "Venusaur"),
    )

    mapped = assign_evolution_metadata(
        build,
        (_edge("bulbasaur", "ivysaur"), _edge("ivysaur", "venusaur")),
    )
    family = [
        row
        for row in mapped.combatants
        if row.evolution_family_id == "bulbasaur-family"
    ]

    assert {(row.display_name, row.evolution_stage) for row in family} == {
        ("Bulbasaur", 1),
        ("Ivysaur", 2),
        ("Venusaur", 3),
    }
    assert len(list(itertools.combinations(family, 2))) == 3


def test_branched_eevee_family_preserves_each_successor() -> None:
    """Branching does not discard any successor or flatten its stage."""
    build = _build(
        _row("eevee", 133, "Eevee"),
        _row("vaporeon", 134, "Vaporeon"),
        _row("jolteon", 135, "Jolteon"),
        _row("flareon", 136, "Flareon"),
    )

    mapped = assign_evolution_metadata(
        build,
        (
            _edge("eevee", "vaporeon"),
            _edge("eevee", "jolteon"),
            _edge("eevee", "flareon"),
        ),
    )

    assert {
        (row.base_species_id, row.evolution_stage, row.evolution_family_id)
        for row in mapped.combatants
    } == {
        ("eevee", 1, "eevee-family"),
        ("vaporeon", 2, "eevee-family"),
        ("jolteon", 2, "eevee-family"),
        ("flareon", 2, "eevee-family"),
    }


def test_forms_inherit_base_species_family_and_stage() -> None:
    """Combat forms remain separate rows but inherit their base-node metadata."""
    build = _build(
        _row("bulbasaur", 1, "Bulbasaur"),
        _row("ivysaur", 2, "Ivysaur"),
        _row("venusaur", 3, "Venusaur"),
        _row("venusaur", 3, "Mega Venusaur", form_name="Mega"),
    )

    mapped = assign_evolution_metadata(
        build,
        (_edge("bulbasaur", "ivysaur"), _edge("ivysaur", "venusaur")),
    )
    venusaur_rows = [
        row for row in mapped.combatants if row.base_species_id == "venusaur"
    ]

    assert {(row.evolution_family_id, row.evolution_stage) for row in venusaur_rows} == {
        ("bulbasaur-family", 3)
    }


def test_unconnected_regional_branches_remain_distinct_families() -> None:
    """Distinct base species join only through an explicitly pinned edge."""
    build = _build(
        _row("diglett", 50, "Diglett"),
        _row("dugtrio", 51, "Dugtrio"),
        _row("wiglett", 960, "Wiglett"),
        _row("wugtrio", 961, "Wugtrio"),
    )

    mapped = assign_evolution_metadata(
        build,
        (_edge("diglett", "dugtrio"), _edge("wiglett", "wugtrio")),
    )
    metadata = {
        row.base_species_id: (row.evolution_family_id, row.evolution_stage)
        for row in mapped.combatants
    }

    assert metadata["diglett"] == ("diglett-family", 1)
    assert metadata["dugtrio"] == ("diglett-family", 2)
    assert metadata["wiglett"] == ("wiglett-family", 1)
    assert metadata["wugtrio"] == ("wiglett-family", 2)


def test_longest_path_and_multiple_roots_are_deterministic() -> None:
    """A convergent DAG uses its longest root distance and canonical first root."""
    build = _build(
        _row("alpha", 4),
        _row("beta", 2),
        _row("gamma", 3),
        _row("shared", 1),
    )
    edges = (
        _edge("beta", "gamma"),
        _edge("gamma", "shared"),
        _edge("alpha", "shared"),
    )

    mapped = assign_evolution_metadata(build, edges)
    metadata = {
        row.base_species_id: (row.evolution_family_id, row.evolution_stage)
        for row in mapped.combatants
    }

    assert metadata == {
        "alpha": ("alpha-family", 1),
        "beta": ("alpha-family", 1),
        "gamma": ("alpha-family", 2),
        "shared": ("alpha-family", 3),
    }


def test_empty_edges_yield_deterministic_singleton_families() -> None:
    """A valid no-edge build still receives normalized deterministic metadata."""
    mapped = assign_evolution_metadata(
        _build(_row("zubat", 41), _row("abra", 63)), ()
    )

    assert [
        (row.base_species_id, row.evolution_family_id, row.evolution_stage)
        for row in mapped.combatants
    ] == [
        ("zubat", "zubat-family", 1),
        ("abra", "abra-family", 1),
    ]


def test_mapping_is_identical_under_shuffled_rows_and_edges() -> None:
    """Canonical output order and metadata never depend on input sequence."""
    rows = (
        _row("venusaur", 3, "Venusaur"),
        _row("bulbasaur", 1, "Bulbasaur"),
        _row("ivysaur", 2, "Ivysaur"),
    )
    edges = (_edge("ivysaur", "venusaur"), _edge("bulbasaur", "ivysaur"))

    forward = assign_evolution_metadata(_build(*rows), edges)
    shuffled = assign_evolution_metadata(_build(*reversed(rows)), tuple(reversed(edges)))

    assert forward == shuffled
    assert [row.combatant_id for row in forward.combatants] == [
        "bulbasaur",
        "ivysaur",
        "venusaur",
    ]


@pytest.mark.parametrize(
    ("edges", "message"),
    (
        (
            (_edge("bulbasaur", "ivysaur"), _edge("bulbasaur", "ivysaur", "other")),
            "duplicate evolution edge: bulbasaur -> ivysaur",
        ),
        ((_edge("bulbasaur", "bulbasaur"),), "self evolution edge: bulbasaur"),
        ((_edge("bulbasaur", "unknown"),), "unknown evolution node: unknown"),
        (
            (
                _edge("bulbasaur", "ivysaur"),
                _edge("ivysaur", "venusaur"),
                _edge("venusaur", "bulbasaur"),
            ),
            "evolution cycle: bulbasaur, ivysaur, venusaur",
        ),
    ),
)
def test_mapping_rejects_invalid_edges(edges: tuple[EvolutionEdge, ...], message: str) -> None:
    """Duplicate, invalid, and cyclic graph definitions fail closed with stable errors."""
    build = _build(
        _row("bulbasaur", 1), _row("ivysaur", 2), _row("venusaur", 3)
    )

    with pytest.raises(ValueError, match=message):
        assign_evolution_metadata(build, edges)


def test_mapping_revalidates_copied_invalid_combatants_and_preserves_exclusions() -> None:
    """The public boundary validates copied rows rather than trusting frozen models."""
    valid = _row("bulbasaur", 1)
    invalid = valid.model_copy(update={"evolution_stage": 0})
    exclusion = ExcludedForm(
        source_form_id="bulbasaur--cosmetic",
        display_name="Bulbasaur Cosmetic",
        reason_code="cosmetic_only",
        reason_text="Not battle distinct.",
        source_ids=("fixture",),
        ruleset_version="fixture",
    )

    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        assign_evolution_metadata(
            RosterBuild(combatants=(invalid,), exclusions=(exclusion,)), ()
        )
