from scripts.lib.pch import Quartet


def test_normalise_both_sides():
    assert Quartet.normalise((1, 2, 3, 4)) == (1, 2, 3, 4)
    assert Quartet.normalise((2, 1, 3, 4)) == (1, 2, 3, 4)
    assert Quartet.normalise((1, 2, 4, 3)) == (1, 2, 3, 4)
    assert Quartet.normalise((2, 1, 4, 3)) == (1, 2, 3, 4)
    assert Quartet.normalise((2, 1, 4, 3)) == (1, 2, 3, 4)
