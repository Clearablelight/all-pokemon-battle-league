"""Crash-recoverable roster bundle publication contracts."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import pytest

from pokemon_league.config import RunConfig
from pokemon_league.roster.publish import (
    preflight_publication_targets,
    publish_roster_bundle,
)
from pokemon_league.roster.validate import validate_roster
from pokemon_league.schemas.roster import RosterBuild
from tests.factories import combatant_factory


def _config() -> RunConfig:
    return RunConfig(
        project_version="1.0.0",
        ruleset_version="2026-08-14.1",
        model_version="2026-08-14.1",
        evidence_cutoff=date(2026, 8, 14),
        timezone="America/Chicago",
        numbered_species_count=1025,
        provisional_species=("Browt", "Pombon", "Gecqua"),
        turn_cap=200,
        seed_root=20260814,
    )


def _build_and_audit():
    build = RosterBuild(
        combatants=(
            combatant_factory(
                ruleset_version="2026-08-14.1",
                source_ids=("fixture",),
            ),
        ),
        exclusions=(),
    )
    return build, validate_roster(build, _config(), False)


def _targets(output: Path, audit: Path) -> tuple[Path, ...]:
    return (
        output / "combatants.parquet",
        output / "combatants.csv",
        output / "excluded-forms.csv",
        audit,
    )


@pytest.mark.parametrize(
    "audit_relative",
    (
        "combatants.parquet",
        "combatants.csv",
        "excluded-forms.csv",
        "nested/../combatants.parquet",
        "nested/../combatants.csv",
        "nested/../excluded-forms.csv",
    ),
)
def test_publication_preflight_rejects_normalized_target_collisions(
    tmp_path: Path, audit_relative: str
) -> None:
    """All four resolved targets must be distinct before any path is created."""
    output = tmp_path / "not-created" / "outputs"
    audit = output / audit_relative

    with pytest.raises(ValueError, match="publication targets must resolve distinctly"):
        preflight_publication_targets(output, audit)

    assert not (tmp_path / "not-created").exists()


def test_publication_preflight_rejects_existing_symlink_target(
    tmp_path: Path,
) -> None:
    """A final target symlink cannot redirect an atomic replacement."""
    output = tmp_path / "outputs"
    output.mkdir()
    actual = tmp_path / "actual.csv"
    actual.write_bytes(b"unchanged\n")
    symlink = output / "combatants.csv"
    symlink.symlink_to(actual)
    audit = tmp_path / "work" / "roster-audit.json"

    with pytest.raises(ValueError, match="publication target is a symlink"):
        preflight_publication_targets(output, audit)

    assert symlink.is_symlink()
    assert actual.read_bytes() == b"unchanged\n"
    assert not audit.parent.exists()


def test_publication_preflight_rejects_normalized_alias_of_symlink_target(
    tmp_path: Path,
) -> None:
    """A `..` alias cannot hide that the audit destination itself is a symlink."""
    actual = tmp_path / "actual-audit.json"
    actual.write_bytes(b"unchanged\n")
    audit_link = tmp_path / "audit-link.json"
    audit_link.symlink_to(actual)
    audit_alias = tmp_path / "not-created" / ".." / "audit-link.json"
    output = tmp_path / "not-created-output"

    with pytest.raises(ValueError, match="publication target is a symlink"):
        preflight_publication_targets(output, audit_alias)

    assert audit_link.is_symlink()
    assert actual.read_bytes() == b"unchanged\n"
    assert not output.exists()


def test_publication_preflight_rejects_cross_filesystem_layout_via_device_helper(
    tmp_path: Path,
) -> None:
    """A bundle spanning devices is rejected because all-or-none rename is impossible."""
    output = tmp_path / "output-parent" / "outputs"
    audit = tmp_path / "audit-parent" / "roster-audit.json"
    output.parent.mkdir()
    audit.parent.mkdir()

    def device_for(path: Path) -> int:
        return 2 if path == audit.parent.resolve() else 1

    with pytest.raises(ValueError, match="one filesystem"):
        preflight_publication_targets(output, audit, device_for_path=device_for)

    assert list(output.parent.iterdir()) == []
    assert list(audit.parent.iterdir()) == []


def test_publish_replace_failure_restores_every_prior_target_and_unrelated_file(
    tmp_path: Path,
) -> None:
    """A mid-publish replace error rolls back exact prior bytes without collateral loss."""
    build, audit_model = _build_and_audit()
    output = tmp_path / "outputs"
    audit = tmp_path / "work" / "roster-audit.json"
    output.mkdir()
    audit.parent.mkdir()
    old_bytes = {
        path: f"old-{index}\n".encode()
        for index, path in enumerate(_targets(output, audit))
    }
    for path, value in old_bytes.items():
        path.write_bytes(value)
    unrelated = output / "keep-me.txt"
    unrelated.write_bytes(b"unrelated\n")
    successful_replaces = 0

    def fail_after_one(source: Path, destination: Path) -> None:
        nonlocal successful_replaces
        if successful_replaces == 1:
            raise OSError("synthetic final replace failure")
        os.replace(source, destination)
        successful_replaces += 1

    result = None
    with pytest.raises(OSError, match="synthetic final replace failure"):
        result = publish_roster_bundle(
            build,
            audit_model,
            {"fixture": "0" * 64},
            output,
            audit,
            replace=fail_after_one,
        )

    assert result is None
    assert {path: path.read_bytes() for path in old_bytes} == old_bytes
    assert unrelated.read_bytes() == b"unrelated\n"
    assert list(tmp_path.rglob(".pokemon-league-transaction-*")) == []
    assert list(tmp_path.rglob("*.tmp")) == []


class SyntheticCrash(BaseException):
    """A process-ending fault that intentionally bypasses in-process rollback."""


def test_next_run_recovers_prepared_crash_before_attempting_new_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A persistent prepared journal restores the old bundle on the next invocation."""
    build, audit_model = _build_and_audit()
    output = tmp_path / "outputs"
    audit = tmp_path / "work" / "roster-audit.json"
    output.mkdir()
    audit.parent.mkdir()
    old_bytes = {
        path: f"old-{index}\n".encode()
        for index, path in enumerate(_targets(output, audit))
    }
    for path, value in old_bytes.items():
        path.write_bytes(value)
    successful_replaces = 0

    def crash_after_one(source: Path, destination: Path) -> None:
        nonlocal successful_replaces
        if successful_replaces == 1:
            raise SyntheticCrash()
        os.replace(source, destination)
        successful_replaces += 1

    with pytest.raises(SyntheticCrash):
        publish_roster_bundle(
            build,
            audit_model,
            {"fixture": "0" * 64},
            output,
            audit,
            replace=crash_after_one,
        )

    assert any(path.read_bytes() != old_bytes[path] for path in old_bytes)
    assert list(tmp_path.rglob(".pokemon-league-transaction-*"))

    def fail_new_stage(*args: object, **kwargs: object) -> None:
        raise RuntimeError("stop after recovery")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", fail_new_stage)
    with pytest.raises(RuntimeError, match="stop after recovery"):
        publish_roster_bundle(
            build,
            audit_model,
            {"fixture": "0" * 64},
            output,
            audit,
        )

    assert {path: path.read_bytes() for path in old_bytes} == old_bytes
    assert list(tmp_path.rglob(".pokemon-league-transaction-*")) == []
    assert list(tmp_path.rglob("*.tmp")) == []
