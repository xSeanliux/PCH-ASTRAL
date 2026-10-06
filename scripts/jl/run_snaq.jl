# SNaQ as the CAMUS paper ran it (gist.github.com/jsdoublel/870d2b53e55b105a7954a7b4db291d60):
# CFs counted from gene trees, search from a start tree. Env JULIA_PROJECT=scripts/jl.
# Usage: run_snaq.jl <gene_trees> <start_tree> <out_prefix> <hmax> <outgroup> <runs> <procs>
using Distributed
gtrees_path, start_path, prefix, hmax, outgroup, runs, procs = ARGS
parse(Int, procs) > 1 && addprocs(parse(Int, procs))  # one SNaQ run per worker
@everywhere using PhyloNetworks, SNaQ, DataFrames

q, t = countquartetsintrees(readmultinewick(gtrees_path); showprogressbar=false)
cfs = filter(r -> r.ngenes > 0, DataFrame(tablequartetCF(q, t); copycols=false))  # unsampled 4-taxon sets carry no CF
net = snaq!(readnewick(start_path), readtableCF(cfs);
    hmax=parse(Int, hmax), runs=parse(Int, runs), outgroup=outgroup, filename=prefix, seed=1)  # the paper's seed=0 means "from the clock"
# snaq! roots at OUT's parent node, a polytomy; root on OUT's edge to match the reference.
try rootatnode!(net, outgroup) catch e; @warn "kept SNaQ's root: $e" end
writenewick(net, prefix * ".net")
