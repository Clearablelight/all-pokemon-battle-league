import tomllib
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from pokemon_league.input_capture import capture_regular_file


class RunConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    project_version: str
    ruleset_version: str
    model_version: str
    evidence_cutoff: date
    timezone: str
    numbered_species_count: int = Field(ge=1)
    provisional_species: tuple[str, ...]
    turn_cap: int = Field(ge=1)
    seed_root: int


def load_run_config(path: Path) -> RunConfig:
    return parse_run_config(capture_regular_file(path).data)


def parse_run_config(data: bytes) -> RunConfig:
    """Parse a run configuration from the exact captured bytes."""
    return RunConfig.model_validate(tomllib.loads(data.decode("utf-8")))
