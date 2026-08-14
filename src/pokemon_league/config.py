import tomllib
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


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
    with path.open("rb") as handle:
        return RunConfig.model_validate(tomllib.load(handle))
