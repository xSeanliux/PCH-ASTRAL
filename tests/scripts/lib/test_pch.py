import pytest
from scripts.lib.pch import (
    Quartet,
    Dataset,
    PCH_W,
    print_quartets_for_astral3,
    print_quartets_for_qfm,
    print_quartets_for_wastral,
)
from scripts.lib.types import Character
from collections import Counter
import polars as pl
from io import StringIO


def test_quartet_normalise_both_sides():
    assert Quartet.normalise((1, 2, 3, 4)) == (1, 2, 3, 4)
    assert Quartet.normalise((2, 1, 3, 4)) == (1, 2, 3, 4)
    assert Quartet.normalise((1, 2, 4, 3)) == (1, 2, 3, 4)
    assert Quartet.normalise((2, 1, 4, 3)) == (1, 2, 3, 4)
    assert Quartet.normalise((2, 1, 4, 3)) == (1, 2, 3, 4)


def test_quartet_taxon_set():
    q = ("a", "b", "c", "d")
    assert Quartet(q).taxon_set == set(q)


@pytest.fixture
def test_print_quartets() -> Counter[Quartet]:
    return Counter[Quartet](
        {
            Quartet(("a", "b", "c", "d")): 2,
            Quartet(("u", "v", "x", "y")): 1,
        }
    )


def test_print_quartets_for_astral_3(test_print_quartets: Counter[Quartet]):
    file = StringIO()
    print_quartets_for_astral3(quartets=test_print_quartets, file=file)
    outstr = file.getvalue()
    print(outstr)
    assert (
        outstr.strip()
        == """
((a,b),(c,d));
((a,b),(c,d));
((u,v),(x,y));
    """.strip()
    )


def test_print_quartets_for_wastral(test_print_quartets: Counter[Quartet]):
    qfile = StringIO()
    wfile = StringIO()
    print_quartets_for_wastral(
        quartets=test_print_quartets, quartet_file=qfile, weight_file=wfile
    )
    qstr = qfile.getvalue()
    wstr = wfile.getvalue()
    assert (
        qstr.strip()
        == """
((a,b),(c,d));
((u,v),(x,y));
""".strip()
    )
    assert (
        wstr.strip()
        == """ 
2
1
""".strip()
    )


def test_print_quartets_for_qfm(test_print_quartets: Counter[Quartet]):
    file = StringIO()
    print_quartets_for_qfm(quartets=test_print_quartets, file=file)
    outstr = file.getvalue()
    print(outstr)
    assert (
        outstr.strip()
        == """
((a,b),(c,d));2.000000
((u,v),(x,y));1.000000
    """.strip()
    )


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
    assert chrs[0] == Character(id="a", feature="abc", weight=4, features={"t1": ["1"]})
    assert chrs[1] == Character(id="b", feature="def", weight=5, features={"t1": ["2"]})
    assert chrs[2] == Character(
        id="c", feature="ghi", weight=6, features={"t1": ["1", "2"]}
    )


def test_pch_astral_w_default():
    dataset = Dataset(
        names=["a", "b", "c", "d"],
        chrs=[
            Character(
                id="t0",
                feature="test",
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
    quartets = PCH_W.get_quartets(dataset)
    assert quartets == {Quartet(("a", "b", "c", "d")): 1}


def test_pch_astral_w_overlap_no_quartet():
    dataset = Dataset(
        names=["a", "b", "c", "d"],
        chrs=[
            Character(
                id="t0",
                feature="test",
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
    quartets = PCH_W.get_quartets(dataset)
    assert quartets == {}


def test_pch_astral_w_overlap_multiple_counts():
    dataset = Dataset(
        names=["a", "b", "c", "d"],
        chrs=[
            Character(
                id="t0",
                feature="test",
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
    quartets = PCH_W.get_quartets(dataset)
    assert quartets == {Quartet(("a", "b", "c", "d")): 4}
