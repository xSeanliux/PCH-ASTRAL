# Upstream issue draft: NetCS rooting (molloy-lab/TREE-QMC)

To file at <https://github.com/molloy-lab/TREE-QMC/issues>. Reproduced on `53b15e5` with the
repo's own `tutorial/NetCS` files.

---

**Title:** `--network`: `--root` segfaults; an invalid `--at` rooting is replaced silently and non-deterministically

**Version:** `53b15e5` (main, 2026-09-22), built with `ENABLE_TOB`.
Built on macOS arm64 (Apple clang) with two local build fixes that do not touch the code
below: `CMAKE_CXX_STANDARD 20 -> 17`, and `int maxlen[fieldcount] = {0};` ->
`std::vector<int> maxlen(fieldcount, 0);` in `src/csvparser.hpp:479`.

**Use case.** We have a tree of blobs rooted on a known outgroup, plus gene trees, and want
the NetCS network rooted on that outgroup.

**What works.** NetCS keeps the rooting of the `--at` tree when it is valid for the network.
From `tutorial/NetCS`, with `tob.tree` rerooted on the edge above `l20`
(`(l20,(<the other six root children>));`):

```
tree-qmc --network -i gt.trees --at rooted_l20.tree -o net.nwk --override
```

```
Checking whether the current rooting is valid ...
Cureent rooting is valid
```

`net.nwk` starts `(l20,(` and is identical across 4 runs. This is what we want; it is not
documented (`--network` and `--at` are also missing from `-h`).

**Problem 1: `--root` segfaults in network mode.**

```
tree-qmc --network -i gt.trees --at tob.tree -o net.nwk --override --root l36
```

```
Rooting species tree at l36
Segmentation fault (exit 139); net.nwk is not written
```

`src/instance.cpp:201-203` calls `output->root_at_clade(outgroup_taxon_set)`, but the
`network` branch (`:157-186`) only sets `output_net`; `output` is still `NULL` (`:56`).

**Problem 2: an invalid rooting is replaced by an arbitrary one, exit 0.**
Root `tob.tree` on the edge above `l34`, a taxon NetCS places below a hybrid node:

```
tree-qmc --network -i gt.trees --at rooted_l34.tree -o net.nwk --override
```

```
Checking whether the current rooting is valid ...
Current rooting is not valid but it is valid semi-directed network;
Perform rerooting on the edge above taxon l24
```

- The new root is not stable: 4 identical runs gave 3 different files.
- The output keeps unary nodes where the old root was, e.g. `(t54,(l35,(l34)))`.
- Exit code is 0, so a caller must parse the log or the Newick to notice.

**Requests.**
1. Make `--root` work with `--network` (or reject it with an error instead of crashing).
2. When the `--at` rooting is invalid, either fail, or pick the new root deterministically
   and say so in a machine-readable way; suppress the unary nodes.
3. Document that the `--at` tree's rooting is kept when valid.

**Minor, same mode.** Hybrid labels are 0-indexed (`#H0`); PhyloNet rejects index 0
("Hybrid node index must be greater than or equal to one").
