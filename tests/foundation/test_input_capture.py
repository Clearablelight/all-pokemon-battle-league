"""One-shot audited input capture contracts."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from pokemon_league import input_capture as capture_module
from pokemon_league.input_capture import capture_regular_file


def test_capture_regular_file_returns_the_exact_bytes_and_digest(tmp_path: Path) -> None:
    """One descriptor read supplies both parser bytes and their audit identity."""
    path = tmp_path / "input.json"
    payload = b'{"fixture":true}\n'
    path.write_bytes(payload)

    captured = capture_regular_file(path)

    assert captured.path == path
    assert captured.data == payload
    assert captured.byte_count == len(payload)
    assert captured.sha256 == hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize(
    "kind",
    ("final-symlink", "parent-symlink", "hidden-symlink", "directory"),
)
def test_capture_regular_file_rejects_unsafe_paths(
    tmp_path: Path, kind: str
) -> None:
    """No-follow traversal never consumes bytes through a symlink or directory."""
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    real_file = real_parent / "input"
    real_file.write_bytes(b"fixture\n")
    if kind == "final-symlink":
        path = tmp_path / "input-link"
        path.symlink_to(real_file)
    elif kind == "parent-symlink":
        alias = tmp_path / "parent-link"
        alias.symlink_to(real_parent, target_is_directory=True)
        path = alias / "input"
    elif kind == "hidden-symlink":
        alias = tmp_path / "parent-link"
        alias.symlink_to(real_parent, target_is_directory=True)
        path = alias / ".." / "real" / "input"
    else:
        path = real_parent

    with pytest.raises(ValueError, match="unsafe regular input"):
        capture_regular_file(path)


def test_capture_regular_file_fails_closed_on_in_place_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A metadata-changing write during descriptor capture cannot be audited as stable."""
    path = tmp_path / "input"
    path.write_bytes(b"before mutation\n")
    real_read = capture_module._read_descriptor

    def read_then_mutate(descriptor: int) -> bytes:
        data = real_read(descriptor)
        path.write_bytes(b"after mutation with different bytes\n")
        return data

    monkeypatch.setattr(capture_module, "_read_descriptor", read_then_mutate)

    with pytest.raises(ValueError, match="changed while being captured"):
        capture_regular_file(path)
