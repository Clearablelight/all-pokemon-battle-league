"""Contract tests for installable package runtime metadata."""

import tomllib
from email import message_from_file
from pathlib import Path

from packaging.requirements import Requirement
from setuptools import build_meta  # type: ignore[import-untyped]


def _requirements(path: Path) -> set[tuple[str, frozenset[str]]]:
    """Normalize direct requirement ranges without depending on their textual order."""
    return {
        (
            requirement.name.lower(),
            frozenset(str(specifier) for specifier in requirement.specifier),
        )
        for raw_line in path.read_text(encoding="utf-8").splitlines()
        if (line := raw_line.strip()) and not line.startswith("#")
        for requirement in [Requirement(line)]
    }


def test_built_metadata_exposes_every_runtime_requirement_from_requirements_in(
    tmp_path: Path,
) -> None:
    """A clean wheel install must receive every production dependency, not dev tools."""
    with Path("pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    assert "dependencies" in pyproject["project"].get("dynamic", [])
    assert pyproject["tool"]["setuptools"]["dynamic"]["dependencies"] == {
        "file": ["requirements.in"]
    }

    dist_info = build_meta.prepare_metadata_for_build_wheel(str(tmp_path))
    with (tmp_path / dist_info / "METADATA").open(encoding="utf-8") as handle:
        metadata = message_from_file(handle)

    assert _requirements(Path("requirements.in")) == {
        (
            Requirement(value).name.lower(),
            frozenset(str(specifier) for specifier in Requirement(value).specifier),
        )
        for value in metadata.get_all("Requires-Dist", [])
    }
