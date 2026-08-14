"""Self-contained ledger/blob bundle verification contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from pokemon_league.sources.bundle import verify_source_bundle


def _write_catalog(path: Path) -> None:
    path.write_text(
        "sources:\n"
        "  - source_id: fixture\n"
        "    url: https://example.test/fixture\n"
        "    source_kind: synthetic-test-only\n"
        "    continuity_id: fixture\n"
        "    required: true\n"
        "    license_note: synthetic test-only source\n",
        encoding="utf-8",
    )


def _write_bundle(
    root: Path,
    *,
    blob_path: Path | None = None,
    sha256: str | None = None,
    payload: bytes = b"synthetic source\n",
) -> tuple[Path, Path, Path, str]:
    root.mkdir(exist_ok=True)
    catalog = root / "sources.yaml"
    ledger = root / "source-ledger.json"
    _write_catalog(catalog)
    digest = sha256 or hashlib.sha256(payload).hexdigest()
    blob = blob_path or root / "blobs" / digest
    blob.parent.mkdir(parents=True, exist_ok=True)
    if not blob.exists():
        blob.write_bytes(payload)
    record = {
        "source_id": "fixture",
        "url": "https://example.test/fixture",
        "source_kind": "synthetic-test-only",
        "continuity_id": "fixture",
        "retrieved_at": "2026-08-14T12:00:00Z",
        "sha256": digest,
        "byte_count": len(payload),
        "blob_path": str(blob),
        "required": True,
        "license_note": "synthetic test-only source",
        "publication_date": None,
    }
    ledger.write_text(json.dumps({"records": [record]}) + "\n", encoding="utf-8")
    return catalog, ledger, blob, digest


def test_source_bundle_accepts_only_expected_content_addressed_blob(
    tmp_path: Path,
) -> None:
    """A valid bundle resolves one verified source ID inside its own blob root."""
    root = tmp_path / "sources"
    catalog, ledger, _, _ = _write_bundle(root)

    bundle = verify_source_bundle(root, ledger, catalog, date(2026, 8, 14))

    assert bundle.verified_source_ids == frozenset({"fixture"})
    assert bundle.coverage_gaps == ()


@pytest.mark.parametrize(
    "ledger_payload",
    (
        [],
        {},
        {"records": [], "unexpected": True},
    ),
)
def test_source_bundle_requires_exact_records_envelope(
    tmp_path: Path, ledger_payload: object
) -> None:
    """Publication verification rejects legacy arrays and noncanonical envelopes."""
    root = tmp_path / "sources"
    catalog, ledger, _, _ = _write_bundle(root)
    ledger.write_text(json.dumps(ledger_payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="exact records envelope"):
        verify_source_bundle(root, ledger, catalog, date(2026, 8, 14))


def test_source_bundle_requires_records_envelope_value_to_be_a_list(
    tmp_path: Path,
) -> None:
    """The one allowed envelope key must contain a JSON list, not another type."""
    root = tmp_path / "sources"
    catalog, ledger, _, _ = _write_bundle(root)
    ledger.write_text(json.dumps({"records": {}}) + "\n", encoding="utf-8")

    with pytest.raises(TypeError, match="exact records envelope"):
        verify_source_bundle(root, ledger, catalog, date(2026, 8, 14))


def test_source_bundle_rejects_outside_blob_even_when_checksum_matches(
    tmp_path: Path,
) -> None:
    """A ledger cannot validate arbitrary matching bytes outside its frozen source root."""
    outside = tmp_path / "outside.bin"
    root = tmp_path / "sources"
    catalog, ledger, _, _ = _write_bundle(root, blob_path=outside)

    with pytest.raises(ValueError, match="unexpected blob_path for source_id: fixture"):
        verify_source_bundle(root, ledger, catalog, date(2026, 8, 14))


def test_source_bundle_rejects_wrong_digest_filename(tmp_path: Path) -> None:
    """A matching file under blobs still must be named by the ledger SHA-256."""
    root = tmp_path / "sources"
    wrong = root / "blobs" / "wrong-name"
    catalog, ledger, _, _ = _write_bundle(root, blob_path=wrong)

    with pytest.raises(ValueError, match="unexpected blob_path for source_id: fixture"):
        verify_source_bundle(root, ledger, catalog, date(2026, 8, 14))


def test_source_bundle_rejects_expected_name_that_is_a_symlink_escape(
    tmp_path: Path,
) -> None:
    """An expected lexical filename cannot follow a symlink to outside evidence."""
    payload = b"synthetic source\n"
    digest = hashlib.sha256(payload).hexdigest()
    outside = tmp_path / "outside.bin"
    outside.write_bytes(payload)
    root = tmp_path / "sources"
    expected = root / "blobs" / digest
    expected.parent.mkdir(parents=True)
    expected.symlink_to(outside)
    catalog, ledger, _, _ = _write_bundle(
        root, blob_path=expected, sha256=digest, payload=payload
    )

    with pytest.raises(ValueError, match="symlink blob_path for source_id: fixture"):
        verify_source_bundle(root, ledger, catalog, date(2026, 8, 14))


def test_source_bundle_rejects_declared_intermediate_symlink_alias(
    tmp_path: Path,
) -> None:
    """A lexical alias to blobs is unsafe even when it resolves to the exact blob."""
    root = tmp_path / "sources"
    catalog, ledger, _, digest = _write_bundle(root)
    alias = root / "blob-alias"
    alias.symlink_to(root / "blobs", target_is_directory=True)
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    payload["records"][0]["blob_path"] = str(alias / digest)
    ledger.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="symlink blob_path for source_id: fixture"):
        verify_source_bundle(root, ledger, catalog, date(2026, 8, 14))


def test_source_bundle_rejects_symlink_hidden_before_dotdot(
    tmp_path: Path,
) -> None:
    """Lexical walking inspects a symlink even when later `..` resolves it away."""
    root = tmp_path / "sources"
    catalog, ledger, _, digest = _write_bundle(root)
    child = root / "child"
    child.mkdir()
    alias = root / "child-alias"
    alias.symlink_to(child, target_is_directory=True)
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    payload["records"][0]["blob_path"] = str(
        alias / ".." / "blobs" / digest
    )
    ledger.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="symlink blob_path for source_id: fixture"):
        verify_source_bundle(root, ledger, catalog, date(2026, 8, 14))


def test_source_bundle_rejects_declared_symlink_root_alias(
    tmp_path: Path,
) -> None:
    """A declared root alias cannot hide a lexical symlink in the blob path."""
    root = tmp_path / "sources"
    catalog, ledger, _, digest = _write_bundle(root)
    alias_root = tmp_path / "sources-alias"
    alias_root.symlink_to(root, target_is_directory=True)
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    payload["records"][0]["blob_path"] = str(alias_root / "blobs" / digest)
    ledger.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="symlink blob_path for source_id: fixture"):
        verify_source_bundle(root, ledger, catalog, date(2026, 8, 14))


def test_source_bundle_rejects_symlinked_sources_root(tmp_path: Path) -> None:
    """The bundle root itself must be a lexical non-symlink path."""
    root = tmp_path / "sources"
    catalog, ledger, _, _ = _write_bundle(root)
    alias_root = tmp_path / "sources-alias"
    alias_root.symlink_to(root, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink sources root"):
        verify_source_bundle(alias_root, ledger, catalog, date(2026, 8, 14))


def test_source_bundle_rejects_non_sha256_identity(tmp_path: Path) -> None:
    """Ledger content identities must be exact lowercase SHA-256 hex strings."""
    root = tmp_path / "sources"
    catalog, ledger, _, _ = _write_bundle(root, sha256="not-a-sha256")

    with pytest.raises(ValueError, match="sha256"):
        verify_source_bundle(root, ledger, catalog, date(2026, 8, 14))
