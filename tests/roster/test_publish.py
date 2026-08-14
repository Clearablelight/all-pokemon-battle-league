"""Crash-recoverable roster bundle publication contracts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import pytest

from pokemon_league.config import RunConfig
from pokemon_league.roster import publish as publish_module
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


def test_publication_preflight_rejects_symlinked_parent_component(
    tmp_path: Path,
) -> None:
    """Final destinations cannot traverse a symlinked parent directory."""
    real_audit_parent = tmp_path / "real-audit"
    real_audit_parent.mkdir()
    alias_parent = tmp_path / "audit-alias"
    alias_parent.symlink_to(real_audit_parent, target_is_directory=True)
    output = tmp_path / "outputs"
    audit = alias_parent / "roster-audit.json"

    with pytest.raises(ValueError, match="symlink component"):
        preflight_publication_targets(output, audit)

    assert not output.exists()
    assert list(real_audit_parent.iterdir()) == []


def test_publication_preflight_rejects_symlink_parent_hidden_before_dotdot(
    tmp_path: Path,
) -> None:
    """A normalized audit path cannot erase a traversed lexical symlink component."""
    child = tmp_path / "child"
    child.mkdir()
    alias = tmp_path / "child-alias"
    alias.symlink_to(child, target_is_directory=True)
    output = tmp_path / "outputs"
    audit = alias / ".." / "work" / "roster-audit.json"

    with pytest.raises(ValueError, match="symlink component"):
        preflight_publication_targets(output, audit)

    assert not output.exists()
    assert not (tmp_path / "work").exists()


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


def test_same_target_set_cannot_enter_recovery_while_lock_is_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Per-target OS locks reject a second publisher before transaction recovery."""
    build, audit_model = _build_and_audit()
    output = tmp_path / "outputs"
    audit = tmp_path / "work" / "roster-audit.json"
    targets = preflight_publication_targets(output, audit)
    recovery_entered = False

    def record_recovery(*args: object, **kwargs: object) -> None:
        nonlocal recovery_entered
        recovery_entered = True

    monkeypatch.setattr(publish_module, "_recover_transaction", record_recovery)
    with (
        publish_module.acquire_publication_locks(targets),
        pytest.raises(RuntimeError, match="publication target is locked"),
    ):
        publish_roster_bundle(
            build,
            audit_model,
            {"fixture": "0" * 64},
            output,
            audit,
        )

    assert recovery_entered is False
    assert not output.exists()
    assert not audit.parent.exists()


def test_target_sets_sharing_outputs_conflict_even_with_different_audits(
    tmp_path: Path,
) -> None:
    """Locks are keyed per target rather than only by the four-target set hash."""
    output = tmp_path / "outputs"
    first = preflight_publication_targets(output, tmp_path / "audit-a.json")
    second = preflight_publication_targets(output, tmp_path / "audit-b.json")

    with (
        publish_module.acquire_publication_locks(first),
        pytest.raises(RuntimeError, match="publication target is locked"),
        publish_module.acquire_publication_locks(second),
    ):
        raise AssertionError("overlapping lock unexpectedly acquired")


def test_disjoint_target_sets_can_hold_locks_concurrently(tmp_path: Path) -> None:
    """Unrelated publication bundles do not block one another."""
    first = preflight_publication_targets(
        tmp_path / "one" / "outputs", tmp_path / "one" / "audit.json"
    )
    second = preflight_publication_targets(
        tmp_path / "two" / "outputs", tmp_path / "two" / "audit.json"
    )

    with (
        publish_module.acquire_publication_locks(first),
        publish_module.acquire_publication_locks(second),
    ):
        pass


def test_publication_locks_release_after_exception(tmp_path: Path) -> None:
    """An exceptional exit releases all advisory locks for the next publisher."""
    targets = preflight_publication_targets(
        tmp_path / "outputs", tmp_path / "audit.json"
    )

    with (
        pytest.raises(RuntimeError, match="synthetic locked section failure"),
        publish_module.acquire_publication_locks(targets),
    ):
        raise RuntimeError("synthetic locked section failure")

    with publish_module.acquire_publication_locks(targets):
        pass


def test_publication_locks_conflict_across_processes(tmp_path: Path) -> None:
    """The lock is enforced by the OS, not merely by Python process-local state."""
    output = tmp_path / "outputs"
    audit = tmp_path / "audit.json"
    targets = preflight_publication_targets(output, audit)
    child_code = (
        "from pathlib import Path\n"
        "from pokemon_league.roster.publish import "
        "acquire_publication_locks, preflight_publication_targets\n"
        "import sys\n"
        "targets = preflight_publication_targets(Path(sys.argv[1]), Path(sys.argv[2]))\n"
        "with acquire_publication_locks(targets):\n"
        "    print('locked', flush=True)\n"
        "    sys.stdin.readline()\n"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", child_code, str(output), str(audit)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == "locked"
        with (
            pytest.raises(RuntimeError, match="publication target is locked"),
            publish_module.acquire_publication_locks(targets),
        ):
            raise AssertionError("cross-process lock unexpectedly acquired")
    finally:
        stdout, stderr = child.communicate("\n", timeout=10)
    assert child.returncode == 0, stdout + stderr


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


def test_publication_backups_are_independent_of_in_place_original_changes(
    tmp_path: Path,
) -> None:
    """A post-backup in-place mutation cannot alter bytes used for rollback."""
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

    def mutate_original_then_fail(source: Path, destination: Path) -> None:
        _targets(output, audit)[3].write_bytes(b"mutated after backup\n")
        raise OSError("synthetic failure after mutation")

    with pytest.raises(OSError, match="synthetic failure after mutation"):
        publish_roster_bundle(
            build,
            audit_model,
            {"fixture": "0" * 64},
            output,
            audit,
            replace=mutate_original_then_fail,
        )

    assert {path: path.read_bytes() for path in old_bytes} == old_bytes


def test_writer_failure_removes_only_newly_created_parent_directories(
    tmp_path: Path,
) -> None:
    """Rollback removes empty parents created for this bundle, deepest first."""
    build, audit_model = _build_and_audit()
    output = tmp_path / "new" / "published" / "outputs"
    audit = tmp_path / "new" / "work" / "audit" / "roster-audit.json"

    def fail_first_replace(source: Path, destination: Path) -> None:
        raise OSError("synthetic first replace failure")

    with pytest.raises(OSError, match="synthetic first replace failure"):
        publish_roster_bundle(
            build,
            audit_model,
            {"fixture": "0" * 64},
            output,
            audit,
            replace=fail_first_replace,
        )

    assert not (tmp_path / "new").exists()
    assert list(tmp_path.rglob(".pokemon-league-transaction-*")) == []


def test_writer_failure_preserves_preexisting_empty_parent_directories(
    tmp_path: Path,
) -> None:
    """Rollback never removes empty directories that predated the transaction."""
    build, audit_model = _build_and_audit()
    output = tmp_path / "outputs"
    audit_parent = tmp_path / "work"
    output.mkdir()
    audit_parent.mkdir()
    audit = audit_parent / "roster-audit.json"

    def fail_first_replace(source: Path, destination: Path) -> None:
        raise OSError("synthetic first replace failure")

    with pytest.raises(OSError, match="synthetic first replace failure"):
        publish_roster_bundle(
            build,
            audit_model,
            {"fixture": "0" * 64},
            output,
            audit,
            replace=fail_first_replace,
        )

    assert output.is_dir() and list(output.iterdir()) == []
    assert audit_parent.is_dir() and list(audit_parent.iterdir()) == []


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


@pytest.mark.parametrize(
    "damage", ("missing", "corrupt", "extra", "symlink", "metadata")
)
def test_recovery_prevalidates_every_backup_before_mutating_any_target(
    tmp_path: Path, damage: str
) -> None:
    """One invalid later backup fails closed without partially restoring targets."""
    build, audit_model = _build_and_audit()
    output = tmp_path / "outputs"
    audit = tmp_path / "work" / "roster-audit.json"
    output.mkdir()
    audit.parent.mkdir()
    for index, path in enumerate(_targets(output, audit)):
        path.write_bytes(f"old-{index}\n".encode())
    transaction = preflight_publication_targets(output, audit).transaction_root
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

    later_backup = transaction / "backups" / "3"
    if damage == "missing":
        later_backup.unlink()
    elif damage == "corrupt":
        later_backup.write_bytes(b"corrupt backup\n")
    elif damage == "extra":
        (transaction / "backups" / "unexpected").write_bytes(b"unsafe extra\n")
    elif damage == "symlink":
        later_backup.unlink()
        later_backup.symlink_to(transaction / "backups" / "2")
    else:
        journal_path = transaction / "journal.json"
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        journal["backups"][3]["sha256"] = "invalid"
        journal_path.write_text(json.dumps(journal) + "\n", encoding="utf-8")
    bytes_before_recovery = {
        path: path.read_bytes() for path in _targets(output, audit)
    }

    with pytest.raises(ValueError, match="publication.*backup"):
        publish_roster_bundle(
            build,
            audit_model,
            {"fixture": "0" * 64},
            output,
            audit,
        )

    assert {
        path: path.read_bytes() for path in _targets(output, audit)
    } == bytes_before_recovery
    assert transaction.is_dir()


def test_crash_recovery_removes_only_parents_created_by_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prepared recovery finds stable transaction state and cleans created parents."""
    build, audit_model = _build_and_audit()
    output = tmp_path / "new" / "published" / "outputs"
    audit = tmp_path / "new" / "work" / "audit" / "roster-audit.json"
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

    assert not (tmp_path / "new").exists()
    assert list(tmp_path.rglob(".pokemon-league-transaction-*")) == []
