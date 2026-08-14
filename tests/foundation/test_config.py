from datetime import date
from pathlib import Path

from pokemon_league.config import load_run_config


def test_run_config_freezes_cutoff_and_numeric_rules() -> None:
    config = load_run_config(Path("tests/fixtures/run.toml"))
    assert config.evidence_cutoff == date(2026, 8, 14)
    assert config.timezone == "America/Chicago"
    assert config.numbered_species_count == 1025
    assert config.provisional_species == ("Browt", "Pombon", "Gecqua")
    assert config.turn_cap == 200
    assert config.seed_root == 20260814
