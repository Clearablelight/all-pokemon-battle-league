"""Contract tests for immutable source snapshots and their provenance ledger."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.request import Request

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from pokemon_league.sources.snapshot import (
    MAX_RESPONSE_BYTES,
    SourceRecord,
    SourceSpec,
    fetch_https_bytes,
    snapshot_sources,
)
from pokemon_league.sources.validate import main, validate_source_ledger

FETCHED_AT = datetime(2026, 8, 14, tzinfo=UTC)


def source_spec(**overrides: object) -> SourceSpec:
    """Return a valid source specification whose fields are explicit in each test."""
    values: dict[str, object] = {
        "source_id": "fixture",
        "url": "https://example.test/fixture",
        "source_kind": "technical",
        "continuity_id": "shared",
        "required": True,
        "license_note": "test fixture",
    }
    values.update(overrides)
    return SourceSpec.model_validate(values)


def source_record(blob: Path, payload: bytes, **overrides: object) -> SourceRecord:
    """Build a ledger record whose digest is independently hand-derived from payload."""
    values: dict[str, object] = {
        "source_id": "fixture",
        "url": "https://example.test/fixture",
        "source_kind": "technical",
        "continuity_id": "shared",
        "retrieved_at": FETCHED_AT,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
        "blob_path": str(blob),
        "required": True,
        "license_note": "test fixture",
    }
    values.update(overrides)
    return SourceRecord.model_validate(values)


def test_snapshot_is_content_addressed_and_repeatable(tmp_path: Path) -> None:
    """A changed write path must not make a repeatable payload produce new provenance."""
    spec = source_spec(url="memory://fixture")
    fetch = lambda _: b"Bulbasaur\n"

    first = snapshot_sources((spec,), tmp_path, FETCHED_AT, fetch)
    second = snapshot_sources((spec,), tmp_path, FETCHED_AT, fetch)

    assert first == second
    assert (
        first[0].sha256
        == "398c945e5593870adcad9c81aa3ba801a6c6359ea3a2b57878cceb1ebcc68e40"
    )
    assert (tmp_path / "blobs" / first[0].sha256).read_bytes() == b"Bulbasaur\n"


def test_snapshot_sorts_records_by_source_id(tmp_path: Path) -> None:
    """Input traversal order must not leak into the published source ledger."""
    specs = (source_spec(source_id="zulu"), source_spec(source_id="alpha"))

    records = snapshot_sources(specs, tmp_path, FETCHED_AT, lambda url: url.encode())

    assert [record.source_id for record in records] == ["alpha", "zulu"]


def test_snapshot_reuses_a_preexisting_valid_blob_without_rewriting(
    tmp_path: Path,
) -> None:
    """A valid existing digest path must remain immutable when a source repeats."""
    payload = b"Bulbasaur\n"
    digest = hashlib.sha256(payload).hexdigest()
    blob = tmp_path / "blobs" / digest
    blob.parent.mkdir()
    blob.write_bytes(payload)
    original_mtime = blob.stat().st_mtime_ns

    records = snapshot_sources(
        (source_spec(),), tmp_path, FETCHED_AT, lambda _: payload
    )

    assert records[0].blob_path == str(blob)
    assert blob.read_bytes() == payload
    assert blob.stat().st_mtime_ns == original_mtime


def test_snapshot_rejects_corrupt_existing_digest_path(tmp_path: Path) -> None:
    """Digest-named corrupt bytes must not be silently accepted or overwritten."""
    payload = b"Bulbasaur\n"
    digest = hashlib.sha256(payload).hexdigest()
    blob = tmp_path / "blobs" / digest
    blob.parent.mkdir()
    blob.write_bytes(b"corrupt")

    with pytest.raises(ValueError, match="corrupt source blob"):
        snapshot_sources((source_spec(),), tmp_path, FETCHED_AT, lambda _: payload)

    assert blob.read_bytes() == b"corrupt"


def test_models_are_frozen_forbid_unknown_fields_and_allow_unknown_dates() -> None:
    """Provenance models must reject accidental schema drift without inventing dates."""
    spec = source_spec()

    with pytest.raises(ValidationError, match="frozen"):
        spec.source_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="not_reviewed"):
        SourceSpec.model_validate({**spec.model_dump(), "not_reviewed": True})

    record = source_record(Path("/tmp/blob"), b"fixture")
    assert spec.publication_date is None
    assert record.publication_date is None


@pytest.mark.parametrize(
    ("change", "message"),
    (
        ({"continuity_id": ""}, "continuity_id"),
        ({"source_id": "fixture", "blob_path": "/missing"}, "missing required blob"),
        ({"sha256": "0" * 64}, "sha256 mismatch"),
        ({"byte_count": 999}, "byte_count mismatch"),
        ({"publication_date": date(2026, 8, 15)}, "publication_date"),
    ),
)
def test_validate_source_ledger_rejects_invalid_required_provenance(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    """Each invalid ledger branch must prevent a required source from appearing covered."""
    payload = b"Bulbasaur\n"
    blob = tmp_path / "blobs" / hashlib.sha256(payload).hexdigest()
    blob.parent.mkdir()
    blob.write_bytes(payload)

    with pytest.raises(ValueError, match=message):
        validate_source_ledger((source_record(blob, payload, **change),))


def test_validate_source_ledger_rejects_duplicate_ids(tmp_path: Path) -> None:
    """Duplicate source IDs would make a ledger's coverage claim ambiguous."""
    payload = b"Bulbasaur\n"
    blob = tmp_path / "blob"
    blob.write_bytes(payload)
    record = source_record(blob, payload)

    with pytest.raises(ValueError, match="duplicate source_id: fixture"):
        validate_source_ledger((record, record))


def test_validate_source_ledger_keeps_optional_missing_source_as_coverage_gap(
    tmp_path: Path,
) -> None:
    """An optional absent source is reported as a gap instead of failing required coverage."""
    record = source_record(tmp_path / "not-snapshotted", b"fixture", required=False)

    gaps = validate_source_ledger((record,))

    assert gaps == ("fixture",)


class FakeResponse:
    """Minimal streaming HTTP response double for transport-boundary tests."""

    def __init__(self, status: int, chunks: list[bytes]) -> None:
        self.status = status
        self._chunks = iter(chunks)

    def read(self, size: int) -> bytes:
        del size
        return next(self._chunks, b"")

    def close(self) -> None:
        pass


class StatusFailureResponse:
    """Response double whose status lookup fails after transport has succeeded."""

    def __init__(self) -> None:
        self.closed = False

    @property
    def status(self) -> int:
        raise RuntimeError("synthetic status failure")

    def read(self, size: int) -> bytes:
        del size
        return b""

    def close(self) -> None:
        self.closed = True


def test_fetch_https_bytes_closes_response_when_status_lookup_fails() -> None:
    """A response acquired before status inspection must always be closed on failure."""
    response = StatusFailureResponse()

    with pytest.raises(RuntimeError, match="synthetic status failure"):
        fetch_https_bytes(
            "https://example.test/status-failure", transport=lambda _: response
        )

    assert response.closed


def test_fetch_https_bytes_rejects_non_https_before_transport() -> None:
    """An insecure URL must never reach the network transport."""
    called = False

    def transport(_: object) -> FakeResponse:
        nonlocal called
        called = True
        return FakeResponse(200, [b"unexpected"])

    with pytest.raises(ValueError, match="HTTPS"):
        fetch_https_bytes("http://example.test", transport=transport)

    assert not called


def test_fetch_https_bytes_retries_transient_statuses_with_bounded_backoff() -> None:
    """A transient 429/5xx must retry exactly three times after the initial attempt."""
    requests: list[Request] = []
    waits: list[float] = []
    responses = iter(
        [
            FakeResponse(429, []),
            FakeResponse(503, []),
            FakeResponse(500, []),
            FakeResponse(200, [b"Bulba", b"saur\n"]),
        ]
    )

    def transport(request: Request) -> FakeResponse:
        requests.append(request)
        return next(responses)

    payload = fetch_https_bytes(
        "https://example.test/source", transport=transport, sleep=waits.append
    )

    assert payload == b"Bulbasaur\n"
    assert len(requests) == 4
    assert waits == [1.0, 2.0, 3.0]
    user_agent = requests[0].get_header("User-agent")
    assert user_agent is not None
    assert "pokemon-league" in user_agent


def test_fetch_https_bytes_does_not_retry_other_client_errors() -> None:
    """A permanent client error must not create surprise repeated requests."""
    attempts = 0

    def transport(_: object) -> FakeResponse:
        nonlocal attempts
        attempts += 1
        return FakeResponse(404, [])

    with pytest.raises(ValueError, match="HTTP 404"):
        fetch_https_bytes("https://example.test/missing", transport=transport)

    assert attempts == 1


def test_fetch_https_bytes_stops_streaming_at_the_response_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A response that crosses the cap must fail before storing unbounded content."""
    monkeypatch.setattr("pokemon_league.sources.snapshot.MAX_RESPONSE_BYTES", 5)

    with pytest.raises(ValueError, match="response exceeds"):
        fetch_https_bytes(
            "https://example.test/large",
            transport=lambda _: FakeResponse(200, [b"123", b"456"]),
        )

    assert MAX_RESPONSE_BYTES == 100 * 1024 * 1024


def test_catalog_contains_baseline_and_pinned_technical_records() -> None:
    """The source catalog must preserve every design baseline plus pinned tool records."""
    catalog = yaml.safe_load(Path("config/sources.yaml").read_text(encoding="utf-8"))
    records = catalog["sources"]
    urls = {record["url"] for record in records}

    assert len(records) == 15
    assert len({record["source_id"] for record in records}) == len(records)
    assert all(record["continuity_id"].strip() for record in records)
    assert {
        "https://www.pokemon.com/us/pokedex",
        "https://windswaves.pokemon.com/en-us/?pubDate=20260306",
        "https://www.pokemon.com/us/pokemon-news/pokemon-champions-releases-on-nintendo-switch-and-nintendo-switch-2-on-april-8-2026",
        "https://legends.pokemon.com/en-us/mega-pokemon",
        "https://swordshield.pokemon.com/en-us/gameplay/gigantamax/",
        "https://legends.arceus.pokemon.com/en-us/gameplay/",
        "https://parents.pokemon.com/en-us/animation/",
        "https://legends.arceus.pokemon.com/en-us/pokemon/arceus/",
        "https://play.pokemonshowdown.com/data/",
        "https://github.com/smogon/pokemon-showdown/blob/master/sim/SIMULATOR.md",
        "https://github.com/smogon/pokemon-showdown/blob/master/data/FORMES.md",
        "https://github.com/smogon/pokemon-showdown/blob/master/sim/TEAMS.md",
        "https://github.com/smogon/damage-calc/blob/master/README.md",
    } <= urls
    assert any(
        record.get("commit") == "b22742debfdce6e640193384f5731b9030f9cb6e"
        for record in records
    )
    assert any(
        record.get("package") == "@smogon/calc" and record.get("version") == "0.11.0"
        for record in records
    )


def test_offline_cli_reports_sorted_unsnapshotted_catalog_ids_without_fetching(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Offline validation must use only local ledger bytes and name every missing ID."""
    config_path = tmp_path / "config" / "sources.yaml"
    config_path.parent.mkdir()
    config_path.write_text(
        "sources:\n"
        "  - source_id: zulu\n"
        "    url: https://example.test/zulu\n"
        "    source_kind: technical\n"
        "    continuity_id: shared\n"
        "    required: true\n"
        "    license_note: test\n"
        "  - source_id: alpha\n"
        "    url: https://example.test/alpha\n"
        "    source_kind: technical\n"
        "    continuity_id: shared\n"
        "    required: true\n"
        "    license_note: test\n",
        encoding="utf-8",
    )
    ledger_path = tmp_path / "source-ledger.json"
    ledger_path.write_text(json.dumps([]), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert main(["--ledger", str(ledger_path), "--offline"]) == 2
    assert (
        capsys.readouterr().err == "missing or unsnapshotted source IDs: alpha, zulu\n"
    )


def test_offline_cli_names_a_ledger_record_with_no_required_blob(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A stale required record must be reported as unsnapshotted, not as a raw traceback."""
    config_path = tmp_path / "config" / "sources.yaml"
    config_path.parent.mkdir()
    config_path.write_text(
        "sources:\n"
        "  - source_id: fixture\n"
        "    url: https://example.test/fixture\n"
        "    source_kind: technical\n"
        "    continuity_id: shared\n"
        "    required: true\n"
        "    license_note: test\n",
        encoding="utf-8",
    )
    ledger_path = tmp_path / "source-ledger.json"
    ledger_path.write_text(
        json.dumps(
            [source_record(tmp_path / "missing", b"fixture").model_dump(mode="json")]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert main(["--ledger", str(ledger_path), "--offline"]) == 2
    assert capsys.readouterr().err == "missing or unsnapshotted source IDs: fixture\n"


def test_offline_module_command_has_no_import_runtime_warning(tmp_path: Path) -> None:
    """The documented module command must not emit an import-order runtime warning."""
    environment = {**os.environ, "PYTHONPATH": str(Path.cwd() / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pokemon_league.sources.validate",
            "--ledger",
            str(tmp_path / "missing-ledger.json"),
            "--offline",
        ],
        cwd=Path.cwd(),
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "RuntimeWarning" not in result.stderr
    assert result.stderr.startswith("missing or unsnapshotted source IDs: ")
