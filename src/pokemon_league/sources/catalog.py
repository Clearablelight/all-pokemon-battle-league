"""Strict parsing for the production source catalog."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml  # type: ignore[import-untyped]

from pokemon_league.input_capture import capture_regular_file
from pokemon_league.sources.snapshot import SourceSpec

PIN_METADATA_KEYS = frozenset({"commit", "package", "version"})


def load_source_catalog(path: Path) -> tuple[SourceSpec, ...]:
    """Load an exact catalog, permitting only documented non-schema pin metadata."""
    return parse_source_catalog(capture_regular_file(path).data)


def parse_source_catalog(data: bytes) -> tuple[SourceSpec, ...]:
    """Parse the strict catalog from exact captured bytes."""
    payload: Any = yaml.safe_load(data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("source catalog must be an object")
    unknown_top = sorted(set(payload) - {"sources"})
    if unknown_top:
        raise ValueError(
            f"unknown source catalog top-level keys: {', '.join(unknown_top)}"
        )
    if set(payload) != {"sources"} or not isinstance(payload["sources"], list):
        raise ValueError("source catalog must contain exactly one sources list")

    allowed = set(SourceSpec.model_fields) | PIN_METADATA_KEYS
    specs: list[SourceSpec] = []
    for index, value in enumerate(payload["sources"], start=1):
        if not isinstance(value, dict):
            raise TypeError(f"source catalog row {index} must be an object")
        unknown_row = sorted(set(value) - allowed)
        if unknown_row:
            raise ValueError(
                f"unknown source catalog row keys: {', '.join(unknown_row)}"
            )
        _validate_pin_metadata(value, index)
        selected = {
            key: item for key, item in value.items() if key in SourceSpec.model_fields
        }
        _validate_strict_scalars(selected, index)
        for field in (
            "source_id",
            "url",
            "source_kind",
            "continuity_id",
            "license_note",
        ):
            selected[field] = _required_text(selected.get(field), field, index)
        _validate_https_url(str(selected["url"]), index)
        specs.append(SourceSpec.model_validate(selected))

    _reject_duplicate_ids(specs)
    _reject_duplicate_urls(specs)
    return tuple(sorted(specs, key=lambda spec: spec.source_id))


def _required_text(value: object, field: str, row: int) -> str:
    if not isinstance(value, str) or not (trimmed := value.strip()):
        raise ValueError(f"{field} on source catalog row {row} must not be blank")
    return trimmed


def _validate_strict_scalars(selected: dict[str, object], row: int) -> None:
    if type(selected.get("required")) is not bool:
        raise ValueError(f"required must be a boolean on source catalog row {row}")
    publication_date = selected.get("publication_date")
    if publication_date is not None and (
        not isinstance(publication_date, date)
        or isinstance(publication_date, datetime)
    ):
        raise ValueError(
            f"publication_date must be a date on source catalog row {row}"
        )


def _validate_pin_metadata(value: dict[str, object], row: int) -> None:
    for key in PIN_METADATA_KEYS & set(value):
        _required_text(value[key], key, row)


def _validate_https_url(url: str, row: int) -> None:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError(f"source catalog URL on row {row} must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"source catalog URL on row {row} must not contain credentials")


def _normalized_url(url: str) -> tuple[str, str, int | None, str, str]:
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/")
    return (
        parsed.scheme.lower(),
        (parsed.hostname or "").lower(),
        parsed.port,
        path,
        parsed.query,
    )


def _reject_duplicate_ids(specs: list[SourceSpec]) -> None:
    seen: set[str] = set()
    for spec in specs:
        if spec.source_id in seen:
            raise ValueError(f"duplicate catalog source_id: {spec.source_id}")
        seen.add(spec.source_id)


def _reject_duplicate_urls(specs: list[SourceSpec]) -> None:
    seen: dict[tuple[str, str, int | None, str, str], str] = {}
    for spec in specs:
        normalized = _normalized_url(spec.url)
        if normalized in seen:
            raise ValueError(
                "duplicate normalized catalog URL for source IDs: "
                f"{seen[normalized]}, {spec.source_id}"
            )
        seen[normalized] = spec.source_id
