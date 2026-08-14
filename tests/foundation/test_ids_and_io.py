"""Contract tests for canonical identifiers and atomic artifact writes."""

import hashlib
import json
import string
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

import pokemon_league.io as league_io
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


def test_atomic_json_creates_nested_destination_parents(tmp_path: Path) -> None:
    """A first manifest export must not require its output tree to pre-exist."""
    path = tmp_path / "nested" / "manifests" / "record.json"

    digest = write_json_atomic(path, {"combatant_id": "bulbasaur"})

    assert path.read_bytes() == b'{"combatant_id": "bulbasaur"}\n'
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()


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
    metadata = pq.ParquetFile(parquet_path).metadata
    assert all(
        metadata.row_group(0).column(index).compression == "ZSTD"
        for index in range(metadata.num_columns)
    )


def test_atomic_table_creates_separate_nested_destination_parents(tmp_path: Path) -> None:
    """Parquet and CSV exports may have different, initially absent parent trees."""
    parquet_path = tmp_path / "tables" / "parquet" / "combatants.parquet"
    csv_path = tmp_path / "exports" / "csv" / "combatants.csv"

    digests = write_table_atomic(
        pd.DataFrame({"combatant_id": ["bulbasaur"]}), parquet_path, csv_path
    )

    assert parquet_path.exists()
    assert csv_path.read_bytes() == b"combatant_id\nbulbasaur\n"
    assert digests["parquet"] == hashlib.sha256(parquet_path.read_bytes()).hexdigest()
    assert digests["csv"] == hashlib.sha256(csv_path.read_bytes()).hexdigest()


def test_atomic_table_rejects_equivalent_destinations_before_mutation(
    tmp_path: Path,
) -> None:
    """One path must never be atomically replaced first as Parquet then as CSV."""
    normalized_path = tmp_path / "exports" / "combatants.parquet"
    aliased_path = tmp_path / "exports" / ".." / "exports" / "combatants.parquet"

    with pytest.raises(ValueError, match="distinct"):
        write_table_atomic(
            pd.DataFrame({"combatant_id": ["bulbasaur"]}),
            normalized_path,
            aliased_path,
        )

    assert not (tmp_path / "exports").exists()


def test_atomic_json_removes_sibling_temp_after_serialization_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed serializer must not leave an orphan beside a future manifest."""
    path = tmp_path / "record.json"

    def fail_dump(*args: object, **kwargs: object) -> None:
        raise RuntimeError("synthetic serialization failure")

    monkeypatch.setattr(league_io.json, "dump", fail_dump)

    with pytest.raises(RuntimeError, match="synthetic serialization failure"):
        write_json_atomic(path, {"combatant_id": "bulbasaur"})

    assert not path.exists()
    assert list(tmp_path.glob(".record.json.*.tmp")) == []


def test_atomic_table_can_omit_csv(tmp_path: Path) -> None:
    """Intermediate parquet-only exports must not report a CSV digest."""
    parquet_path = tmp_path / "combatants.parquet"

    digests = write_table_atomic(pd.DataFrame({"combatant_id": ["bulbasaur"]}), parquet_path)

    assert set(digests) == {"parquet"}
    assert digests["parquet"] == hashlib.sha256(parquet_path.read_bytes()).hexdigest()
