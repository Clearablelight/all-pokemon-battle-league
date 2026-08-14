"""Content-addressed, immutable snapshots of cited source material."""

import hashlib
import os
import time
from collections.abc import Callable, Sequence
from datetime import date, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict

MAX_RESPONSE_BYTES = 100 * 1024 * 1024
RESPONSE_CHUNK_BYTES = 1024 * 1024
MAX_ATTEMPTS = 4
PROJECT_USER_AGENT = "pokemon-league-source-snapshotter/1.0"

FetchBytes = Callable[[str], bytes]
Sleep = Callable[[float], None]


class StreamingResponse(Protocol):
    """The small streaming response surface required by the snapshot fetcher."""

    def read(self, size: int) -> bytes: ...

    def close(self) -> None: ...


class HTTPResponse(StreamingResponse, Protocol):
    """A streaming response with an HTTP status code."""

    status: int


Transport = Callable[[Request], HTTPResponse]


class SourceSpec(BaseModel):
    """A source requested for snapshotting, before bytes are retrieved."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str
    url: str
    source_kind: str
    continuity_id: str
    required: bool
    license_note: str
    publication_date: date | None = None


class SourceRecord(BaseModel):
    """Immutable provenance for one content-addressed source snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str
    url: str
    source_kind: str
    continuity_id: str
    retrieved_at: datetime
    sha256: str
    byte_count: int
    blob_path: str
    required: bool
    license_note: str
    publication_date: date | None = None


def _bounded_backoff(retry_number: int) -> float:
    """Return a deterministic bounded delay for the next transient attempt."""
    return min(float(retry_number), 3.0)


def _read_response(response: StreamingResponse) -> bytes:
    """Read a response incrementally and reject a payload over the fixed cap."""
    chunks: list[bytes] = []
    total = 0
    while chunk := response.read(RESPONSE_CHUNK_BYTES):
        total += len(chunk)
        if total > MAX_RESPONSE_BYTES:
            raise ValueError(f"response exceeds {MAX_RESPONSE_BYTES} byte limit")
        chunks.append(chunk)
    return b"".join(chunks)


def fetch_https_bytes(
    url: str,
    *,
    transport: Transport | None = None,
    sleep: Sleep | None = None,
) -> bytes:
    """Fetch HTTPS source bytes with bounded reads and deterministic transient retries."""
    if urlsplit(url).scheme != "https":
        raise ValueError("source URL must use HTTPS")

    opener: Transport = transport if transport is not None else urlopen  # type: ignore[assignment]
    pause = sleep if sleep is not None else time.sleep
    request = Request(url, headers={"User-Agent": PROJECT_USER_AGENT})
    for attempt in range(MAX_ATTEMPTS):
        response: StreamingResponse | None = None
        try:
            response = opener(request)
            status = response.status
        except HTTPError as error:
            response = error
            status = error.code

        try:
            if response is None:
                raise AssertionError("transport returned no response")
            if status == 429 or 500 <= status <= 599:
                if attempt + 1 < MAX_ATTEMPTS:
                    pause(_bounded_backoff(attempt + 1))
                    continue
                raise ValueError(f"HTTP {status} after {MAX_ATTEMPTS} attempts")
            if 400 <= status <= 499:
                raise ValueError(f"HTTP {status}")
            if not 200 <= status <= 299:
                raise ValueError(f"HTTP {status}")
            return _read_response(response)
        finally:
            if response is not None:
                response.close()

    raise AssertionError("retry loop did not return or raise")


def _file_digest_and_size(path: Path) -> tuple[str, int]:
    """Return a file's digest and byte count without loading it all into memory."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(RESPONSE_CHUNK_BYTES):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _store_immutable_blob(blob: Path, payload: bytes, digest: str) -> None:
    """Publish a fully written digest blob once, or verify its existing bytes."""
    blob.parent.mkdir(parents=True, exist_ok=True)
    if blob.exists():
        if not blob.is_file() or _file_digest_and_size(blob) != (digest, len(payload)):
            raise ValueError(f"corrupt source blob at {blob}")
        return

    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            dir=blob.parent, prefix=f".{digest}.", delete=False
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o444)
        if temporary_path is None:
            raise AssertionError("temporary blob path was not created")
        try:
            os.link(temporary_path, blob)
        except FileExistsError:
            if not blob.is_file() or _file_digest_and_size(blob) != (
                digest,
                len(payload),
            ):
                raise ValueError(f"corrupt source blob at {blob}")
    except BaseException:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
    if temporary_path is not None:
        temporary_path.unlink(missing_ok=True)


def snapshot_sources(
    specs: Sequence[SourceSpec],
    root: Path,
    fetched_at: datetime,
    fetch: FetchBytes,
) -> tuple[SourceRecord, ...]:
    """Fetch source bytes into content-addressed blobs and return sorted provenance."""
    records: list[SourceRecord] = []
    for spec in sorted(specs, key=lambda item: item.source_id):
        payload = fetch(spec.url)
        digest = hashlib.sha256(payload).hexdigest()
        blob = root / "blobs" / digest
        _store_immutable_blob(blob, payload, digest)
        records.append(
            SourceRecord(
                source_id=spec.source_id,
                url=spec.url,
                source_kind=spec.source_kind,
                continuity_id=spec.continuity_id,
                retrieved_at=fetched_at,
                sha256=digest,
                byte_count=len(payload),
                blob_path=str(blob),
                required=spec.required,
                license_note=spec.license_note,
                publication_date=spec.publication_date,
            )
        )
    return tuple(records)
