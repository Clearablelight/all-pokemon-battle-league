"""Crash-recoverable publication of the four-file final roster bundle."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]

from pokemon_league.io import write_csv_atomic, write_json_atomic, write_table_atomic
from pokemon_league.roster.validate import RosterAudit
from pokemon_league.schemas.roster import Combatant, ExcludedForm, RosterBuild

DeviceForPath = Callable[[Path], int]
Replace = Callable[[Path, Path], None]
TRANSACTION_PREFIX = ".pokemon-league-transaction-"
JOURNAL_NAME = "journal.json"


@dataclass(frozen=True)
class PublicationTargets:
    """Four normalized targets and deterministic same-filesystem transaction state."""

    paths: tuple[Path, Path, Path, Path]
    target_set_hash: str
    transaction_root: Path


def preflight_publication_targets(
    output: Path,
    audit_path: Path,
    *,
    device_for_path: DeviceForPath | None = None,
) -> PublicationTargets:
    """Reject collisions, symlink targets, and cross-device layouts without mutation."""
    raw_targets = (
        output / "combatants.parquet",
        output / "combatants.csv",
        output / "excluded-forms.csv",
        audit_path,
    )
    lexical_targets = tuple(Path(os.path.abspath(target)) for target in raw_targets)
    for raw_target, target in zip(raw_targets, lexical_targets, strict=True):
        if raw_target.is_symlink() or target.is_symlink():
            raise ValueError(f"publication target is a symlink: {raw_target}")
        if target.exists() and not target.is_file():
            raise ValueError(f"publication target is not a regular file: {raw_target}")
    resolved = tuple(target.resolve(strict=False) for target in lexical_targets)
    if len(set(resolved)) != 4:
        raise ValueError("publication targets must resolve distinctly")

    existing_ancestors = tuple(_nearest_existing_ancestor(path) for path in resolved)
    device = device_for_path or (lambda path: path.stat().st_dev)
    devices = {device(path) for path in existing_ancestors}
    if len(devices) != 1:
        raise ValueError("publication targets must reside on one filesystem")

    target_set_hash = hashlib.sha256(
        "\0".join(str(path) for path in resolved).encode("utf-8")
    ).hexdigest()
    transaction_root = existing_ancestors[0] / (
        f"{TRANSACTION_PREFIX}{target_set_hash[:24]}"
    )
    if any(
        path == transaction_root or transaction_root in path.parents
        for path in resolved
    ):
        raise ValueError("publication target overlaps transaction state")
    if transaction_root.is_symlink():
        raise ValueError(f"publication transaction path is a symlink: {transaction_root}")
    return PublicationTargets(
        paths=(resolved[0], resolved[1], resolved[2], resolved[3]),
        target_set_hash=target_set_hash,
        transaction_root=transaction_root,
    )


def publish_roster_bundle(
    build: RosterBuild,
    audit: RosterAudit,
    input_hashes: dict[str, str],
    output: Path,
    audit_path: Path,
    *,
    replace: Replace = os.replace,
    device_for_path: DeviceForPath | None = None,
) -> RosterAudit:
    """Stage, journal, publish, or exactly roll back one validated roster bundle."""
    targets = preflight_publication_targets(
        output, audit_path, device_for_path=device_for_path
    )
    _recover_transaction(targets)
    transaction = targets.transaction_root
    transaction.mkdir(mode=0o700)
    try:
        staged = transaction / "staged"
        backups = transaction / "backups"
        staged.mkdir()
        backups.mkdir()
        _write_journal(targets, "building", ())
        published_audit = _stage_artifacts(
            build, audit, input_hashes, targets, staged
        )
        existed = tuple(path.exists() for path in targets.paths)
        _backup_existing_targets(targets.paths, existed, backups)
        _write_journal(targets, "prepared", existed)
        for path in targets.paths:
            _ensure_parent(path.parent)
            if path.is_symlink():
                raise ValueError(f"publication target became a symlink: {path}")
        for index, target in enumerate(targets.paths):
            replace(staged / str(index), target)
            _fsync_file(target)
            _fsync_directory(staged)
            _fsync_directory(target.parent)
        _write_journal(targets, "committed", existed)
    except Exception:
        journal_path = transaction / JOURNAL_NAME
        if journal_path.is_file() and not journal_path.is_symlink():
            journal = _read_journal(targets)
            if journal["state"] == "prepared":
                _restore_prepared(targets, journal)
            else:
                _cleanup_transaction(targets)
        else:
            _cleanup_transaction(targets)
        raise

    _cleanup_transaction(targets)
    return published_audit


def _stage_artifacts(
    build: RosterBuild,
    audit: RosterAudit,
    input_hashes: dict[str, str],
    targets: PublicationTargets,
    staged: Path,
) -> RosterAudit:
    combatants = _frame_for_models(build.combatants, Combatant)
    exclusions = _frame_for_models(build.exclusions, ExcludedForm)
    parquet_hash = write_table_atomic(combatants, staged / "0")["parquet"]
    combatants_csv_hash = write_csv_atomic(_csv_frame(combatants), staged / "1")
    exclusions_csv_hash = write_csv_atomic(_csv_frame(exclusions), staged / "2")
    output_hashes = {
        "combatants.csv": combatants_csv_hash,
        "combatants.parquet": parquet_hash,
        "excluded-forms.csv": exclusions_csv_hash,
    }
    published_audit = audit.model_copy(
        update={"input_hashes": input_hashes, "output_hashes": output_hashes}
    )
    write_json_atomic(staged / "3", published_audit.model_dump(mode="json"))
    for index in range(4):
        _fsync_file(staged / str(index))
    _fsync_directory(staged)
    _fsync_directory(targets.transaction_root)
    return published_audit


def _frame_for_models[ManifestRow: (Combatant, ExcludedForm)](
    rows: Sequence[ManifestRow], model_type: type[ManifestRow]
) -> pd.DataFrame:
    values = [row.model_dump(mode="json") for row in rows]
    return pd.DataFrame(values, columns=list(model_type.model_fields))


def _csv_frame(frame: pd.DataFrame) -> pd.DataFrame:
    exported = frame.copy()
    for column in exported.columns:
        if any(isinstance(value, (list, tuple)) for value in exported[column]):
            exported[column] = exported[column].map(
                lambda value: (
                    json.dumps(sorted(value), ensure_ascii=False, separators=(",", ":"))
                    if isinstance(value, (list, tuple))
                    else value
                )
            )
    return exported


def _backup_existing_targets(
    targets: tuple[Path, Path, Path, Path],
    existed: tuple[bool, ...],
    backups: Path,
) -> None:
    for index, (target, was_present) in enumerate(zip(targets, existed, strict=True)):
        if not was_present:
            continue
        backup = backups / str(index)
        try:
            os.link(target, backup)
        except OSError as error:
            if error.errno not in {errno.EPERM, errno.EACCES, errno.EMLINK}:
                raise
            shutil.copyfile(target, backup)
        _fsync_file(backup)
    _fsync_directory(backups)


def _write_journal(
    targets: PublicationTargets, state: str, existed: tuple[bool, ...]
) -> None:
    payload = {
        "version": 1,
        "target_set_hash": targets.target_set_hash,
        "artifact_count": 4,
        "state": state,
        "existed": list(existed),
    }
    write_json_atomic(targets.transaction_root / JOURNAL_NAME, payload)
    _fsync_directory(targets.transaction_root)
    _fsync_directory(targets.transaction_root.parent)


def _read_journal(targets: PublicationTargets) -> dict[str, object]:
    journal_path = targets.transaction_root / JOURNAL_NAME
    if not journal_path.is_file() or journal_path.is_symlink():
        raise ValueError("publication transaction is missing a safe journal")
    payload = json.loads(journal_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != {
        "version",
        "target_set_hash",
        "artifact_count",
        "state",
        "existed",
    }:
        raise ValueError("invalid publication transaction journal schema")
    if payload["version"] != 1 or payload["artifact_count"] != 4:
        raise ValueError("unsupported publication transaction journal")
    if payload["target_set_hash"] != targets.target_set_hash:
        raise ValueError("publication transaction target set mismatch")
    if payload["state"] not in {"building", "prepared", "committed"}:
        raise ValueError("invalid publication transaction state")
    existed = payload["existed"]
    if not isinstance(existed, list) or any(type(value) is not bool for value in existed):
        raise ValueError("invalid publication transaction existence map")
    if payload["state"] in {"prepared", "committed"} and len(existed) != 4:
        raise ValueError("invalid publication transaction existence map")
    if payload["state"] == "building" and existed:
        raise ValueError("invalid building transaction existence map")
    return payload


def _recover_transaction(targets: PublicationTargets) -> None:
    transaction = targets.transaction_root
    if not transaction.exists():
        return
    if transaction.is_symlink() or not transaction.is_dir():
        raise ValueError(f"unsafe publication transaction path: {transaction}")
    journal = _read_journal(targets)
    state = journal["state"]
    if state == "prepared":
        _restore_prepared(targets, journal)
    elif state in {"building", "committed"}:
        _cleanup_transaction(targets)
    else:
        raise AssertionError("validated transaction state was not handled")


def _restore_prepared(
    targets: PublicationTargets, journal: dict[str, object]
) -> None:
    existed = journal["existed"]
    if not isinstance(existed, list):
        raise TypeError("journal existence map was not validated")
    backups = targets.transaction_root / "backups"
    for index, (target, was_present) in enumerate(
        zip(targets.paths, existed, strict=True)
    ):
        if was_present:
            backup = backups / str(index)
            if backup.is_symlink() or not backup.is_file():
                raise ValueError(f"missing safe publication backup at index {index}")
            _ensure_parent(target.parent)
            restore = targets.transaction_root / f"restore-{index}.tmp"
            restore.unlink(missing_ok=True)
            try:
                os.link(backup, restore)
            except OSError:
                shutil.copyfile(backup, restore)
            _fsync_file(restore)
            _fsync_directory(targets.transaction_root)
            os.replace(restore, target)
            _fsync_file(target)
            _fsync_directory(targets.transaction_root)
            _fsync_directory(target.parent)
        elif target.exists() or target.is_symlink():
            if target.is_symlink() or not target.is_file():
                raise ValueError(f"unsafe newly published target at index {index}")
            target.unlink()
            _fsync_directory(target.parent)
    _cleanup_transaction(targets)


def _cleanup_transaction(targets: PublicationTargets) -> None:
    transaction = targets.transaction_root
    if transaction.is_symlink():
        raise ValueError(f"unsafe publication transaction path: {transaction}")
    if transaction.exists():
        shutil.rmtree(transaction)
        _fsync_directory(transaction.parent)


def _nearest_existing_ancestor(path: Path) -> Path:
    candidate = path.parent
    while not candidate.exists():
        if candidate.parent == candidate:
            raise ValueError(f"no existing ancestor for publication target: {path}")
        candidate = candidate.parent
    if candidate.is_symlink():
        candidate = candidate.resolve(strict=True)
    if not candidate.is_dir():
        raise ValueError(f"publication ancestor is not a directory: {candidate}")
    return candidate.resolve(strict=True)


def _ensure_parent(path: Path) -> None:
    missing: list[Path] = []
    candidate = path
    while not candidate.exists():
        missing.append(candidate)
        candidate = candidate.parent
    if not candidate.is_dir():
        raise ValueError(f"publication parent ancestor is not a directory: {candidate}")
    for directory in reversed(missing):
        directory.mkdir()
        _fsync_directory(directory)
        _fsync_directory(directory.parent)


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
