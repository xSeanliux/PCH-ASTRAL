import sys


def test_model_has_no_inference_imports():
    # model/ describes the run space; it must not know how runs happen.
    for name in list(sys.modules):
        if name.startswith("scripts.lib.inference") or name == "scripts.lib.experiment":
            del sys.modules[name]
    import scripts.lib.model.guide_tree  # noqa: F401
    import scripts.lib.model.strategies  # noqa: F401

    loaded = {n for n in sys.modules if n.startswith("scripts.lib.")}
    assert not {n for n in loaded if n.startswith("scripts.lib.inference")}
    assert "scripts.lib.experiment" not in loaded
