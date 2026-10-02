import subprocess
import sys


def test_model_has_no_inference_imports():
    # model/ describes the run space; it must not know how runs happen. A fresh
    # subprocess (not sys.modules surgery) is the only clean way to check this:
    # mutating sys.modules in-process risks leaving half-imported modules behind.
    script = (
        "import sys\n"
        "import scripts.lib.model.guide_tree\n"
        "import scripts.lib.model.strategies\n"
        "loaded = {n for n in sys.modules if n.startswith('scripts.lib.')}\n"
        "assert not {n for n in loaded if n.startswith('scripts.lib.inference')}\n"
        "assert 'scripts.lib.experiment' not in loaded\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
