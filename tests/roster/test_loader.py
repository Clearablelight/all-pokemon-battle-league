"""Strict CSV loader tests for audited form-decision catalogs."""

from pathlib import Path

import pytest

from pokemon_league.roster.loader import DECISION_CSV_HEADER, load_form_decisions_csv

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "roster" / "decisions.csv"
PRODUCTION_PATH = Path(__file__).parents[2] / "config" / "roster-decisions.csv"


def test_loader_accepts_fixture_and_production_catalog_with_identical_schema() -> None:
    """Fixture and checked-in catalog use the one production CSV boundary."""
    fixture = load_form_decisions_csv(FIXTURE_PATH)
    production = load_form_decisions_csv(PRODUCTION_PATH)

    assert len(fixture) == len(production) == 8
    assert fixture[0].reason_code is None
    assert fixture[0].required_form_item is None
    assert tuple(FIXTURE_PATH.open(encoding="utf-8").readline().strip().split(",")) == (
        DECISION_CSV_HEADER
    )
    assert (
        tuple(PRODUCTION_PATH.open(encoding="utf-8").readline().strip().split(","))
        == DECISION_CSV_HEADER
    )


def test_loader_rejects_malformed_header(tmp_path: Path) -> None:
    """Header order and spelling are a schema boundary, not best-effort input."""
    malformed = tmp_path / "decisions.csv"
    malformed.write_text(
        FIXTURE_PATH.read_text(encoding="utf-8").replace(
            "source_form_id", "source_id", 1
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="exact ordered header"):
        load_form_decisions_csv(malformed)


def test_loader_rejects_empty_source_id_slot(tmp_path: Path) -> None:
    """A pipe separator may not silently discard an empty provenance ID."""
    malformed = tmp_path / "decisions.csv"
    malformed.write_text(
        FIXTURE_PATH.read_text(encoding="utf-8").replace(
            "official-pokedex-venusaur\n",
            "official-pokedex-venusaur| \n",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="empty source_ids slot"):
        load_form_decisions_csv(malformed)


def test_loader_rejects_noncanonical_boolean(tmp_path: Path) -> None:
    """CSV flags accept only explicit lowercase true or false values."""
    malformed = tmp_path / "decisions.csv"
    malformed.write_text(
        FIXTURE_PATH.read_text(encoding="utf-8").replace(
            ",true,true,false,false,false,complete_turn_based,",
            ",yes,true,false,false,false,complete_turn_based,",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must be 'true' or 'false'"):
        load_form_decisions_csv(malformed)
