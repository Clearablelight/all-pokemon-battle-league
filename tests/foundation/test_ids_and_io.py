"""Contract tests for canonical identifiers and atomic artifact writes."""

import hashlib
import json
import string
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from pokemon_league.io import write_json_atomic, write_table_atomic
from pokemon_league.schemas.common import PairKey, stable_id


def test_stable_id_normalizes_display_punctuation() -> None:
    """A punctuation change must not create a second canonical display ID."""
    assert stable_id("Mr. Mime", "Galar") == "mr-mime--galar"


def test_pair_key_rejects_self_pairs() -> None:
    """A pair generator must never turn a self comparison into a real matchup."""
    with pytest.raises(ValueError, match="self-pairs are forbidden"):
        PairKey.of("bulbasaur", "bulbasaur")


@given(
    left=st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=12),
    right=st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=12),
)
def test_pair_key_value_is_invariant_under_reversed_input(
    left: str, right: str
) -> None:
    """Reversed roster traversal must address the same unordered artifact."""
    assume(left != right)
    assert PairKey.of(left, right).value == PairKey.of(right, left).value


def test_atomic_json_is_canonical_and_returns_final_file_hash(tmp_path: Path) -> None:
    """Manifest hashing must describe the atomically replaced final bytes."""
    path = tmp_path / "record.json"
    digest = write_json_atomic(path, {"b": 2, "a": 1})

    expected = b'{"a": 1, "b": 2}\n'
    assert path.read_bytes() == expected
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1, "b": 2}
    assert digest == hashlib.sha256(expected).hexdigest()
    assert list(tmp_path.glob(".record.json.*.tmp")) == []


def test_atomic_table_writes_ordered_csv_zstd_parquet_and_final_hashes(
    tmp_path: Path,
) -> None:
    """Published table exports need stable bytes and the requested compression."""
    frame = pd.DataFrame({"z": [2, 1], "a": ["β", "α"]})
    parquet_path = tmp_path / "combatants.parquet"
    csv_path = tmp_path / "combatants.csv"

    digests = write_table_atomic(frame, parquet_path, csv_path)

    assert pd.read_parquet(parquet_path).to_dict("list") == frame.to_dict("list")
    assert pd.read_parquet(parquet_path).columns.tolist() == ["z", "a"]
    assert csv_path.read_bytes() == "z,a\n2,β\n1,α\n".encode()
    assert digests == {
        "parquet": hashlib.sha256(parquet_path.read_bytes()).hexdigest(),
        "csv": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
    }
    assert pd.read_parquet(parquet_path).shape == (2, 2)


def test_atomic_table_can_omit_csv(tmp_path: Path) -> None:
    """Intermediate parquet-only exports must not report a CSV digest."""
    parquet_path = tmp_path / "combatants.parquet"

    digests = write_table_atomic(pd.DataFrame({"combatant_id": ["bulbasaur"]}), parquet_path)

    assert set(digests) == {"parquet"}
    assert digests["parquet"] == hashlib.sha256(parquet_path.read_bytes()).hexdigest()
