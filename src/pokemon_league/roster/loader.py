"""Strict UTF-8 CSV loading for audited form-decision catalogs."""

import csv
import io
from pathlib import Path

from pokemon_league.input_capture import capture_regular_file
from pokemon_league.schemas.roster import FormDecision

DECISION_CSV_HEADER = (
    "source_form_id",
    "inclusion_status",
    "reason_code",
    "reason_text",
    "activation_class",
    "activation_rule",
    "required_form_item",
    "required_form_condition",
    "core_series_player_legal",
    "official_player_controllable",
    "historical",
    "boss_only",
    "provisional",
    "game_profile_status",
    "lore_evidence_status",
    "game_equivalence_hint",
    "lore_equivalence_hint",
    "inclusion_rationale",
    "source_ids",
)
_BOOLEAN_COLUMNS = (
    "core_series_player_legal",
    "official_player_controllable",
    "historical",
    "boss_only",
    "provisional",
)
_OPTIONAL_TEXT_COLUMNS = (
    "reason_code",
    "reason_text",
    "required_form_item",
    "required_form_condition",
    "inclusion_rationale",
)


def load_form_decisions_csv(path: Path) -> tuple[FormDecision, ...]:
    """Load an exact-schema CSV without relaxing audit or provenance fields."""
    return parse_form_decisions_csv(capture_regular_file(path).data)


def parse_form_decisions_csv(data: bytes) -> tuple[FormDecision, ...]:
    """Parse decisions from the same captured bytes used for their audit hash."""
    handle = io.StringIO(data.decode("utf-8"), newline="")
    reader = csv.DictReader(handle)
    if tuple(reader.fieldnames or ()) != DECISION_CSV_HEADER:
        raise ValueError("form-decision CSV must use the exact ordered header")
    decisions: list[FormDecision] = []
    seen_source_ids: set[str] = set()
    for line_number, row in enumerate(reader, start=2):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"malformed form-decision CSV row {line_number}")
        parsed = _parse_row(row, line_number)
        decision = FormDecision.model_validate(parsed)
        if decision.source_form_id in seen_source_ids:
            raise ValueError(
                f"duplicate decision source_form_id: {decision.source_form_id}"
            )
        seen_source_ids.add(decision.source_form_id)
        decisions.append(decision)
    return tuple(decisions)


def _parse_row(
    row: dict[str | None, str | None], line_number: int
) -> dict[str, object]:
    """Decode one exact-schema row before model validation."""
    parsed: dict[str, object] = {
        str(name): value for name, value in row.items() if name is not None
    }
    for column in _BOOLEAN_COLUMNS:
        value = parsed[column]
        if value not in {"true", "false"}:
            raise ValueError(
                f"{column} on line {line_number} must be 'true' or 'false'"
            )
        parsed[column] = value == "true"
    for column in _OPTIONAL_TEXT_COLUMNS:
        value = parsed[column]
        if not isinstance(value, str):
            raise TypeError(f"missing {column} on line {line_number}")
        parsed[column] = value if value.strip() else None
    source_ids = parsed["source_ids"]
    if not isinstance(source_ids, str):
        raise TypeError(f"missing source_ids on line {line_number}")
    parsed["source_ids"] = _parse_source_ids(source_ids, line_number)
    return parsed


def _parse_source_ids(value: str, line_number: int) -> tuple[str, ...]:
    """Split pipe-delimited source IDs without discarding empty slots."""
    parts = value.split("|")
    if any(not part.strip() for part in parts):
        raise ValueError(f"empty source_ids slot on line {line_number}")
    return tuple(part.strip() for part in parts)
