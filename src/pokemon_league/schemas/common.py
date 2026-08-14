"""Common deterministic identifiers used by every matchup track."""

import re
import unicodedata

from pydantic import BaseModel, ConfigDict


def stable_id(*parts: str) -> str:
    """Return a punctuation-insensitive, ASCII identifier for display text."""
    normalized = []
    for part in parts:
        ascii_text = (
            unicodedata.normalize("NFKD", part).encode("ascii", "ignore").decode()
        )
        normalized.append(re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-"))
    return "--".join(normalized)


class PairKey(BaseModel):
    """Canonical identity of an unordered comparison between two combatants."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    combatant_a_id: str
    combatant_b_id: str

    @classmethod
    def of(cls, left_id: str, right_id: str) -> "PairKey":
        """Create the canonical key, rejecting a comparison to oneself."""
        if left_id == right_id:
            raise ValueError("self-pairs are forbidden")
        left, right = sorted((left_id, right_id))
        return cls(combatant_a_id=left, combatant_b_id=right)

    @property
    def value(self) -> str:
        """Return the stable serialized representation of this pair."""
        return f"{self.combatant_a_id}__vs__{self.combatant_b_id}"
