import tomllib
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from pokemon_league.config import load_run_config


def test_run_config_freezes_cutoff_and_numeric_rules() -> None:
    config = load_run_config(Path("tests/fixtures/run.toml"))
    assert config.evidence_cutoff == date(2026, 8, 14)
    assert config.timezone == "America/Chicago"
    assert config.numbered_species_count == 1025
    assert config.provisional_species == ("Browt", "Pombon", "Gecqua")
    assert config.turn_cap == 200
    assert config.seed_root == 20260814


def test_run_config_rejects_mutation() -> None:
    config = load_run_config(Path("tests/fixtures/run.toml"))

    with pytest.raises(ValidationError):
        config.turn_cap = 1


def test_run_config_rejects_unknown_keys(tmp_path: Path) -> None:
    invalid_config = tmp_path / "run.toml"
    invalid_config.write_text(
        Path("tests/fixtures/run.toml").read_text() + "unknown_rule = true\n"
    )

    with pytest.raises(ValidationError):
        load_run_config(invalid_config)


@pytest.mark.parametrize(
    ("field", "valid_value", "invalid_value"),
    (("numbered_species_count", 1025, 0), ("numbered_species_count", 1025, -1),
     ("turn_cap", 200, 0), ("turn_cap", 200, -1)),
)
def test_run_config_rejects_non_positive_numeric_rules(
    tmp_path: Path, field: str, valid_value: int, invalid_value: int
) -> None:
    invalid_config = tmp_path / "run.toml"
    invalid_config.write_text(
        Path("tests/fixtures/run.toml")
        .read_text()
        .replace(f"{field} = {valid_value}", f"{field} = {invalid_value}")
    )

    with pytest.raises(ValidationError):
        load_run_config(invalid_config)


def test_build_backend_is_exactly_pinned() -> None:
    with Path("pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)

    assert pyproject["build-system"]["requires"] == ["setuptools==80.9.0"]
