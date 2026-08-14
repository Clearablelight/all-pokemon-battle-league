"""Strict production source-catalog parsing contracts."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from pokemon_league.sources.catalog import load_source_catalog


def _catalog_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "source_id": " fixture ",
        "url": " https://Example.TEST/reference/ ",
        "source_kind": " official ",
        "continuity_id": " shared ",
        "required": True,
        "license_note": " test-only evidence ",
        "publication_date": date(2026, 8, 14),
    }
    row.update(overrides)
    return row


def _yaml_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).replace("'", "''")
    return f"'{text}'"


def _write_catalog(path: Path, rows: list[dict[str, object]], **top: object) -> None:
    lines = ["sources:"]
    for row in rows:
        first = True
        for key, value in row.items():
            prefix = "  - " if first else "    "
            lines.append(f"{prefix}{key}: {_yaml_scalar(value)}")
            first = False
    for key, value in top.items():
        lines.append(f"{key}: {_yaml_scalar(value)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_catalog_allows_only_documented_pin_metadata_and_trims_text(
    tmp_path: Path,
) -> None:
    """Known pin metadata is ignored without weakening the SourceSpec boundary."""
    path = tmp_path / "sources.yaml"
    _write_catalog(
        path,
        [
            _catalog_row(
                commit=" abc123 ",
                package=" @fixture/package ",
                version=" 1.2.3 ",
            )
        ],
    )

    (spec,) = load_source_catalog(path)

    assert spec.source_id == "fixture"
    assert spec.url == "https://Example.TEST/reference/"
    assert spec.source_kind == "official"
    assert spec.continuity_id == "shared"
    assert spec.license_note == "test-only evidence"
    assert spec.publication_date == date(2026, 8, 14)


@pytest.mark.parametrize(
    ("row_change", "top_change", "message"),
    (
        ({"unexpected": "value"}, {}, "unknown source catalog row keys: unexpected"),
        ({}, {"unexpected": "value"}, "unknown source catalog top-level keys"),
    ),
)
def test_catalog_rejects_unknown_row_and_top_level_keys(
    tmp_path: Path,
    row_change: dict[str, object],
    top_change: dict[str, object],
    message: str,
) -> None:
    """Typos cannot be silently discarded as if they were pin metadata."""
    path = tmp_path / "sources.yaml"
    _write_catalog(path, [_catalog_row(**row_change)], **top_change)

    with pytest.raises(ValueError, match=message):
        load_source_catalog(path)


@pytest.mark.parametrize(
    "field",
    ("source_id", "url", "source_kind", "continuity_id", "license_note"),
)
def test_catalog_rejects_blank_required_text(tmp_path: Path, field: str) -> None:
    """Whitespace-only source identity and evidence fields are never normalized away."""
    path = tmp_path / "sources.yaml"
    _write_catalog(path, [_catalog_row(**{field: "   "})])

    with pytest.raises(ValueError, match=field):
        load_source_catalog(path)


def test_catalog_rejects_non_https_production_url(tmp_path: Path) -> None:
    """Catalog URLs must use HTTPS even when a test injects the fetch function."""
    path = tmp_path / "sources.yaml"
    _write_catalog(path, [_catalog_row(url="http://example.test/reference")])

    with pytest.raises(ValueError, match="HTTPS"):
        load_source_catalog(path)


@pytest.mark.parametrize(
    ("change", "message"),
    (
        ({"required": "true"}, "required must be a boolean"),
        ({"publication_date": "2026-08-14"}, "publication_date must be a date"),
    ),
)
def test_catalog_rejects_coerced_boolean_and_date_types(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    """Quoted scalar lookalikes cannot pass the strict catalog schema."""
    path = tmp_path / "sources.yaml"
    _write_catalog(path, [_catalog_row(**change)])

    with pytest.raises(ValueError, match=message):
        load_source_catalog(path)


def test_catalog_rejects_duplicate_source_ids(tmp_path: Path) -> None:
    """Duplicate source IDs cannot create last-record-wins provenance."""
    path = tmp_path / "sources.yaml"
    _write_catalog(
        path,
        [
            _catalog_row(source_id="duplicate", url="https://example.test/one"),
            _catalog_row(source_id=" duplicate ", url="https://example.test/two"),
        ],
    )

    with pytest.raises(ValueError, match="duplicate catalog source_id: duplicate"):
        load_source_catalog(path)


@pytest.mark.parametrize(
    "alias_url",
    (
        "HTTPS://example.test/reference/",
        "https://EXAMPLE.TEST/reference",
    ),
)
def test_catalog_rejects_duplicate_normalized_urls(
    tmp_path: Path, alias_url: str
) -> None:
    """Scheme/host case and trailing slash aliases identify the same source URL."""
    path = tmp_path / "sources.yaml"
    _write_catalog(
        path,
        [
            _catalog_row(source_id="first", url="https://example.test/reference"),
            _catalog_row(source_id="second", url=alias_url),
        ],
    )

    with pytest.raises(ValueError, match="duplicate normalized catalog URL"):
        load_source_catalog(path)
