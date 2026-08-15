"""Locked, crash-recoverable publication of the four-file roster bundle."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import stat
import tempfile
import unicodedata
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from pokemon_league.io import write_csv_atomic, write_json_atomic, write_table_atomic
from pokemon_league.roster.validate import RosterAudit
from pokemon_league.schemas.roster import Combatant, ExcludedForm, RosterBuild

DeviceForPath = Callable[[Path], int]
Replace = Callable[[Path, Path], None]
TRANSACTION_PREFIX = ".pokemon-league-transaction-"
JOURNAL_NAME = "journal.json"
ARTIFACT_COUNT = 4
JOURNAL_KEYS = {
    "version",
    "target_set_hash",
    "target_spelling_hash",
    "artifact_count",
    "state",
    "existed",
    "backups",
}


@dataclass(frozen=True)
class PublicationTargets:
    """Four normalized targets and deterministic same-filesystem transaction state."""

    paths: tuple[Path, Path, Path, Path]
    target_set_hash: str
    target_spelling_hash: str
    transaction_root: Path
    parent_paths: tuple[Path, ...]
    identity_keys: tuple[str, str, str, str]


def preflight_publication_targets(
    output: Path,
    audit_path: Path,
    *,
    device_for_path: DeviceForPath | None = None,
) -> PublicationTargets:
    """Reject collisions, symlink traversal, and cross-device layouts without writes."""
    raw_targets = (
        output / "combatants.parquet",
        output / "combatants.csv",
        output / "excluded-forms.csv",
        audit_path,
    )
    lexical_targets = tuple(Path(os.path.abspath(target)) for target in raw_targets)
    for raw_target, target in zip(raw_targets, lexical_targets, strict=True):
        symlink = _first_symlink_component(_anchor_lexically(raw_target))
        if symlink is not None:
            if symlink == target:
                raise ValueError(f"publication target is a symlink: {raw_target}")
            raise ValueError(f"publication target has a symlink component: {symlink}")
        if target.exists() and not target.is_file():
            raise ValueError(f"publication target is not a regular file: {raw_target}")
    resolved = tuple(target.resolve(strict=False) for target in lexical_targets)
    identity_keys = tuple(_portable_path_identity(path) for path in resolved)
    if len(set(identity_keys)) != ARTIFACT_COUNT:
        raise ValueError("publication targets must resolve distinctly")
    output_identity = _portable_path_identity_parts(
        Path(os.path.abspath(output)).resolve(strict=False)
    )
    audit_identity = _portable_path_identity_parts(resolved[3])
    if audit_identity[: len(output_identity)] == output_identity:
        raise ValueError("publication audit path must be outside output directory")

    existing_ancestors = tuple(_nearest_existing_ancestor(path) for path in resolved)
    device = device_for_path or (lambda path: path.stat().st_dev)
    devices = {device(path) for path in existing_ancestors}
    if len(devices) != 1:
        raise ValueError("publication targets must reside on one filesystem")

    target_set_hash = hashlib.sha256(
        "\0".join(identity_keys).encode("utf-8")
    ).hexdigest()
    target_spelling_hash = hashlib.sha256(
        "\0".join(str(path) for path in resolved).encode("utf-8")
    ).hexdigest()
    transaction_name = f"{TRANSACTION_PREFIX}{target_set_hash[:24]}"
    transaction_root = _find_or_choose_transaction_root(
        resolved, existing_ancestors, transaction_name
    )
    if any(
        path == transaction_root or transaction_root in path.parents
        for path in resolved
    ):
        raise ValueError("publication target overlaps transaction state")
    if _first_symlink_component(transaction_root) is not None:
        raise ValueError(f"publication transaction path is unsafe: {transaction_root}")
    if device(_nearest_existing_ancestor(transaction_root)) not in devices:
        raise ValueError("publication transaction must reside on target filesystem")
    parent_paths = _fixed_parent_paths(resolved)
    return PublicationTargets(
        paths=(resolved[0], resolved[1], resolved[2], resolved[3]),
        target_set_hash=target_set_hash,
        target_spelling_hash=target_spelling_hash,
        transaction_root=transaction_root,
        parent_paths=parent_paths,
        identity_keys=(
            identity_keys[0],
            identity_keys[1],
            identity_keys[2],
            identity_keys[3],
        ),
    )


@contextmanager
def acquire_publication_locks(targets: PublicationTargets) -> Iterator[None]:
    """Nonblockingly hold one persistent advisory lock per normalized target."""
    lock_root = _safe_lock_root()
    descriptors: list[int] = []
    try:
        identities_and_targets = sorted(
            zip(targets.identity_keys, targets.paths, strict=True)
        )
        for identity, target in identities_and_targets:
            key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
            lock_path = lock_root / key
            flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(lock_path, flags, 0o600)
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) & 0o077
            ):
                os.close(descriptor)
                raise ValueError(f"unsafe publication lock file: {lock_path}")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                os.close(descriptor)
                raise RuntimeError(f"publication target is locked: {target}") from error
            descriptors.append(descriptor)
        yield
    finally:
        for descriptor in reversed(descriptors):
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


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
    with acquire_publication_locks(targets):
        return _publish_locked(build, audit, input_hashes, targets, replace)


def _publish_locked(
    build: RosterBuild,
    audit: RosterAudit,
    input_hashes: dict[str, str],
    targets: PublicationTargets,
    replace: Replace,
) -> RosterAudit:
    _recover_transaction(targets)
    transaction = targets.transaction_root
    transaction.mkdir(mode=0o700)
    try:
        _fsync_directory(transaction.parent)
        staged = transaction / "staged"
        backups = transaction / "backups"
        staged.mkdir()
        backups.mkdir()
        _fsync_directory(transaction)
        _write_journal(targets, "building", (), ())
        published_audit = _stage_artifacts(build, audit, input_hashes, targets, staged)
        existed = _safe_existence_map(targets.paths)
        backup_metadata = _backup_existing_targets(targets.paths, existed, backups)
        _write_journal(
            targets,
            "prepared",
            existed,
            backup_metadata,
        )
        _create_destination_parents(targets)
        for path in targets.paths:
            symlink = _first_symlink_component(path)
            if symlink is not None:
                raise ValueError(f"publication target became unsafe: {symlink}")
        for index, target in enumerate(targets.paths):
            replace(staged / str(index), target)
            _fsync_file(target)
            _fsync_directory(staged)
            _fsync_directory(target.parent)
        _write_journal(
            targets,
            "committed",
            existed,
            backup_metadata,
        )
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
    for index in range(ARTIFACT_COUNT):
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
) -> tuple[dict[str, object] | None, ...]:
    metadata: list[dict[str, object] | None] = []
    for index, (target, was_present) in enumerate(zip(targets, existed, strict=True)):
        if not was_present:
            metadata.append(None)
            continue
        digest, byte_count = _copy_regular_nofollow(target, backups / str(index))
        metadata.append(
            {"index": index, "byte_count": byte_count, "sha256": digest}
        )
    _fsync_directory(backups)
    return tuple(metadata)


def _copy_regular_nofollow(source: Path, destination: Path) -> tuple[str, int]:
    read_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    write_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    source_descriptor = os.open(source, read_flags)
    destination_descriptor: int | None = None
    digest = hashlib.sha256()
    byte_count = 0
    try:
        if not stat.S_ISREG(os.fstat(source_descriptor).st_mode):
            raise ValueError(f"publication source is not a regular file: {source}")
        destination_descriptor = os.open(destination, write_flags, 0o600)
        while chunk := os.read(source_descriptor, 1024 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
            view = memoryview(chunk)
            while view:
                written = os.write(destination_descriptor, view)
                view = view[written:]
        os.fsync(destination_descriptor)
    finally:
        os.close(source_descriptor)
        if destination_descriptor is not None:
            os.close(destination_descriptor)
    return digest.hexdigest(), byte_count


def _write_journal(
    targets: PublicationTargets,
    state: str,
    existed: tuple[bool, ...],
    backups: tuple[dict[str, object] | None, ...],
) -> None:
    payload = {
        "version": 4,
        "target_set_hash": targets.target_set_hash,
        "target_spelling_hash": targets.target_spelling_hash,
        "artifact_count": ARTIFACT_COUNT,
        "state": state,
        "existed": list(existed),
        "backups": list(backups),
    }
    write_json_atomic(targets.transaction_root / JOURNAL_NAME, payload)
    _fsync_directory(targets.transaction_root)
    _fsync_directory(targets.transaction_root.parent)


def _read_journal(targets: PublicationTargets) -> dict[str, object]:
    journal_path = targets.transaction_root / JOURNAL_NAME
    if not journal_path.is_file() or journal_path.is_symlink():
        raise ValueError("publication transaction is missing a safe journal")
    payload: Any = json.loads(journal_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != JOURNAL_KEYS:
        raise ValueError("invalid publication transaction journal schema")
    if payload["version"] != 4 or payload["artifact_count"] != ARTIFACT_COUNT:
        raise ValueError("unsupported publication transaction journal")
    if payload["target_set_hash"] != targets.target_set_hash:
        raise ValueError("publication transaction target set mismatch")
    if payload["target_spelling_hash"] != targets.target_spelling_hash:
        raise ValueError("publication transaction target spelling mismatch")
    if payload["state"] not in {"building", "prepared", "committed"}:
        raise ValueError("invalid publication transaction state")
    _validate_journal_maps(payload, targets)
    return payload


def _validate_journal_maps(
    payload: dict[str, object], targets: PublicationTargets
) -> None:
    existed = payload["existed"]
    backups = payload["backups"]
    if not isinstance(existed, list) or any(type(value) is not bool for value in existed):
        raise ValueError("invalid publication transaction existence map")
    if not isinstance(backups, list):
        raise TypeError("invalid publication transaction backup map")
    if payload["state"] == "building":
        if existed or backups:
            raise ValueError("invalid building publication transaction maps")
        return
    if len(existed) != ARTIFACT_COUNT or len(backups) != ARTIFACT_COUNT:
        raise ValueError("invalid publication transaction artifact maps")
    for index, (was_present, entry) in enumerate(zip(existed, backups, strict=True)):
        if not was_present:
            if entry is not None:
                raise ValueError("invalid publication transaction backup map")
            continue
        if not isinstance(entry, dict) or set(entry) != {
            "index",
            "byte_count",
            "sha256",
        }:
            raise ValueError("invalid publication transaction backup map")
        if entry["index"] != index:
            raise ValueError("invalid publication transaction backup index")
        size = entry["byte_count"]
        digest = entry["sha256"]
        if type(size) is not int or size < 0:
            raise ValueError("invalid publication transaction backup byte count")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("invalid publication transaction backup sha256")


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
    _validate_prepared_backups(targets, journal)
    _validate_restore_destinations(targets, existed)
    restores = _prepare_restore_copies(targets, journal)
    for index, (target, was_present) in enumerate(
        zip(targets.paths, existed, strict=True)
    ):
        if was_present:
            restore = restores[index]
            os.replace(restore, target)
            _fsync_file(target)
            _fsync_directory(targets.transaction_root)
            _fsync_directory(target.parent)
        elif target.exists():
            target.unlink()
            _fsync_directory(target.parent)
    _cleanup_transaction(targets)


def _prepare_restore_copies(
    targets: PublicationTargets, journal: dict[str, object]
) -> dict[int, Path]:
    """Copy and validate the entire restore set before any target is changed."""
    entries = journal["backups"]
    if not isinstance(entries, list):
        raise TypeError("journal backup map was not validated")
    backups = targets.transaction_root / "backups"
    restores: dict[int, Path] = {}
    try:
        for index, entry in enumerate(entries):
            if entry is None:
                continue
            if not isinstance(entry, dict):
                raise TypeError("journal backup map was not validated")
            restore = targets.transaction_root / f"restore-{index}.tmp"
            if restore.is_symlink() or restore.exists():
                if restore.is_symlink() or not restore.is_file():
                    raise ValueError(f"unsafe publication restore copy at index {index}")
                restore.unlink()
                _fsync_directory(targets.transaction_root)
            digest, byte_count = _copy_regular_nofollow(backups / str(index), restore)
            if digest != entry["sha256"] or byte_count != entry["byte_count"]:
                raise ValueError(f"publication backup changed at index {index}")
            _fsync_file(restore)
            _fsync_directory(targets.transaction_root)
            restores[index] = restore
    except Exception:
        for restore in restores.values():
            restore.unlink(missing_ok=True)
        _fsync_directory(targets.transaction_root)
        raise
    return restores


def _validate_prepared_backups(
    targets: PublicationTargets, journal: dict[str, object]
) -> None:
    backups = targets.transaction_root / "backups"
    if backups.is_symlink() or not backups.is_dir():
        raise ValueError("publication backup directory is unsafe or missing")
    entries = journal["backups"]
    if not isinstance(entries, list):
        raise TypeError("journal backup map was not validated")
    expected_names = {
        str(index) for index, entry in enumerate(entries) if entry is not None
    }
    actual_names: set[str] = set()
    with os.scandir(backups) as directory_entries:
        for directory_entry in directory_entries:
            actual_names.add(directory_entry.name)
            if directory_entry.is_symlink() or not directory_entry.is_file(
                follow_symlinks=False
            ):
                raise ValueError("publication backup set contains an unsafe entry")
    if actual_names != expected_names:
        raise ValueError("publication backup set is incomplete or has extra entries")
    for index, entry in enumerate(entries):
        if entry is None:
            continue
        if not isinstance(entry, dict):
            raise TypeError("journal backup map was not validated")
        digest, byte_count = _digest_regular_nofollow(backups / str(index))
        if digest != entry["sha256"] or byte_count != entry["byte_count"]:
            raise ValueError(f"publication backup mismatch at index {index}")


def _validate_restore_destinations(
    targets: PublicationTargets,
    existed: list[object],
) -> None:
    for index, (target, was_present) in enumerate(
        zip(targets.paths, existed, strict=True)
    ):
        symlink = _first_symlink_component(target)
        if symlink is not None:
            raise ValueError(f"unsafe publication restore destination at index {index}")
        if target.exists() and not target.is_file():
            raise ValueError(f"unsafe publication restore destination at index {index}")
        if was_present and not target.parent.is_dir():
            raise ValueError(f"missing publication restore parent at index {index}")


def _digest_regular_nofollow(path: Path) -> tuple[str, int]:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    digest = hashlib.sha256()
    byte_count = 0
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError(f"publication backup is not a regular file: {path}")
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
    finally:
        os.close(descriptor)
    return digest.hexdigest(), byte_count


def _cleanup_transaction(targets: PublicationTargets) -> None:
    transaction = targets.transaction_root
    if transaction.is_symlink():
        raise ValueError(f"unsafe publication transaction path: {transaction}")
    if transaction.exists():
        shutil.rmtree(transaction)
        _fsync_directory(transaction.parent)


def _safe_existence_map(paths: tuple[Path, ...]) -> tuple[bool, ...]:
    existed: list[bool] = []
    for path in paths:
        symlink = _first_symlink_component(path)
        if symlink is not None:
            raise ValueError(f"publication target became unsafe: {symlink}")
        present = path.exists()
        if present and not path.is_file():
            raise ValueError(f"publication target is not a regular file: {path}")
        existed.append(present)
    return tuple(existed)


def _create_destination_parents(targets: PublicationTargets) -> None:
    """Create missing target parents but never claim or later delete them."""
    for index, directory in enumerate(targets.parent_paths):
        if directory.exists():
            if directory.is_symlink() or not directory.is_dir():
                raise ValueError(f"publication parent became unsafe at index {index}")
            continue
        try:
            _mkdir_parent(directory)
        except FileExistsError:
            metadata = os.lstat(directory)
            if not stat.S_ISDIR(metadata.st_mode):
                raise ValueError(
                    f"publication parent became unsafe at index {index}"
                ) from None
            continue
        metadata = os.lstat(directory)
        if not stat.S_ISDIR(metadata.st_mode):
            raise ValueError(f"publication parent became unsafe at index {index}")
        _fsync_directory(directory)
        _fsync_directory(directory.parent)


def _mkdir_parent(directory: Path) -> None:
    directory.mkdir()


def _find_or_choose_transaction_root(
    paths: tuple[Path, ...],
    existing_ancestors: tuple[Path, ...],
    transaction_name: str,
) -> Path:
    candidates: set[Path] = set()
    for path in paths:
        for ancestor in (path.parent, *path.parents):
            candidate = ancestor / transaction_name
            if candidate.exists() or candidate.is_symlink():
                candidates.add(candidate)
    if len(candidates) > 1:
        raise ValueError("multiple publication transaction states found")
    if candidates:
        return next(iter(candidates))
    common = Path(os.path.commonpath([str(path.parent) for path in paths]))
    anchor = common if common.is_dir() else _nearest_existing_ancestor(common)
    if anchor not in existing_ancestors and not anchor.is_dir():
        raise ValueError("publication transaction has no safe anchor")
    return anchor / transaction_name


def _fixed_parent_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    parents: set[Path] = set()
    for path in paths:
        current = path.parent
        while current.parent != current:
            parents.add(current)
            current = current.parent
    return tuple(sorted(parents, key=lambda path: (len(path.parts), str(path))))


def _nearest_existing_ancestor(path: Path) -> Path:
    candidate = path if path.is_dir() else path.parent
    while not candidate.exists():
        if candidate.parent == candidate:
            raise ValueError(f"no existing ancestor for publication target: {path}")
        candidate = candidate.parent
    if candidate.is_symlink() or not candidate.is_dir():
        raise ValueError(f"publication ancestor is not a safe directory: {candidate}")
    return candidate.resolve(strict=True)


def _first_symlink_component(path: Path) -> Path | None:
    anchored = _anchor_lexically(path)
    current = Path(anchored.anchor)
    for part in anchored.parts[1:]:
        if part == "..":
            current = current.parent
            continue
        current /= part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode):
            return current
    return None


def _anchor_lexically(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def _portable_path_identity(path: Path) -> str:
    return "\0".join(_portable_path_identity_parts(path))


def _portable_path_identity_parts(path: Path) -> tuple[str, ...]:
    return tuple(
        unicodedata.normalize("NFC", os.path.normcase(part)).casefold()
        for part in path.parts
    )


def _safe_lock_root() -> Path:
    root = Path(tempfile.gettempdir()) / f"pokemon-league-publication-locks-{os.getuid()}"
    try:
        root.mkdir(mode=0o700)
    except FileExistsError:
        pass
    metadata = os.lstat(root)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        raise ValueError(f"unsafe publication lock namespace: {root}")
    return root


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
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
