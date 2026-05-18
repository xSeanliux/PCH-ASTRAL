import pytest
from scripts.lib.pch import Quartet, Dataset, Character, PCH_ASTRAL_W
import polars as pl


def test_quartet_normalise_both_sides():
    assert Quartet.normalise((1, 2, 3, 4)) == (1, 2, 3, 4)
    assert Quartet.normalise((2, 1, 3, 4)) == (1, 2, 3, 4)
    assert Quartet.normalise((1, 2, 4, 3)) == (1, 2, 3, 4)
    assert Quartet.normalise((2, 1, 4, 3)) == (1, 2, 3, 4)
    assert Quartet.normalise((2, 1, 4, 3)) == (1, 2, 3, 4)


def test_quartet_taxon_set():
    q = ("a", "b", "c", "d")
    return Quartet(q).taxon_set == set(q)


def test_dataset_extract_throws_on_wrong_first_cols():
    df = pl.DataFrame({"id": [1, 2], "feature": [3, 3]})
    with pytest.raises(AssertionError) as e:
        Dataset._extract_names_and_chrs(df)
    assert "expect first three cols" in str(e)


def test_dataset_extract_names_and_chars_output():
    df = pl.DataFrame(
        {
            "id": ["a", "b", "c"],
            "feature": ["abc", "def", "ghi"],
            "weight": [4, 5, 6],
            "t1": ["1", "2", "1/2"],
        }
    )
    names, chrs = Dataset._extract_names_and_chrs(df)
    assert names == ["t1"]
    assert len(chrs) == 3
    assert chrs[0] == Character(weight=4, features={"t1": ["1"]})
    assert chrs[1] == Character(weight=5, features={"t1": ["2"]})
    assert chrs[2] == Character(weight=6, features={"t1": ["1", "2"]})


def test_pch_astral_w_default():
    dataset = Dataset(
        names=["a", "b", "c", "d"],
        chrs=[
            Character(
                features={
                    "a": ["1"],
                    "b": ["1"],
                    "c": ["2"],
                    "d": ["2"],
                },
                weight=1,
            )
        ],
    )
    quartets = PCH_ASTRAL_W.get_quartets(dataset)
    assert quartets == {Quartet(("a", "b", "c", "d")): 1}


def test_pch_astral_w_overlap_no_quartet():
    dataset = Dataset(
        names=["a", "b", "c", "d"],
        chrs=[
            Character(
                features={
                    "a": ["1"],
                    "b": ["1"],
                    "c": ["1", "2"],
                    "d": ["2"],
                },
                weight=1,
            )
        ],
    )
    quartets = PCH_ASTRAL_W.get_quartets(dataset)
    assert quartets == {}


def test_pch_astral_w_overlap_multiple_counts():
    dataset = Dataset(
        names=["a", "b", "c", "d"],
        chrs=[
            Character(
                features={
                    "a": ["0", "1"],
                    "b": ["0", "1"],
                    "c": ["2", "3"],
                    "d": ["2", "3", "4"],
                },
                weight=1,
            )
        ],
    )
    quartets = PCH_ASTRAL_W.get_quartets(dataset)
    assert quartets == {Quartet(("a", "b", "c", "d")): 4}
