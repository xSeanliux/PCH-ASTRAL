#!/bin/bash
# CAMUS network inference — STUB. Wired into the pipeline (CamusRunner) but the
# real quartet-gen + `bin/camus` invocation is future work; see
# spec/camus/inference.md for the intended contract. For now this is a no-op
# that exits 0 so the pipeline can smoke-run the wiring.
#
# Args (from CamusRunner.build_argv): --runid --input --name --output --guide-trees
echo "runCAMUS.sh invoked (stub): $*"
exit 0
