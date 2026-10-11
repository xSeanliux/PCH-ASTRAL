# SNaQ as the CAMUS paper ran it (gist.github.com/jsdoublel/870d2b53e55b105a7954a7b4db291d60):
# CFs counted from gene trees, search from a start tree. Env JULIA_PROJECT=scripts/jl.
# `--choose` redoes only the point-estimate choice from an existing <out_prefix>.networks/.net.
const USAGE = """usage: run_snaq.jl <gene_trees> <start_tree> <out_prefix> <hmax> <outgroup> <runs> <procs>
       run_snaq.jl --choose <out_prefix> <outgroup>"""
using PhyloNetworks

"""
SNaQ's network is semi-directed; a candidate is consistent with `outgroup` if
`rootatnode!` accepts it. Write as `.net` the first consistent candidate, rerooted: the
best, then `.networks` alternatives by -loglik, skipping failed (-1) ones. `.choice` holds
its 0-based `.networks` row, or `none` (then no `.net`). No `.networks` (a tree): `.net`.
"""
function choose(prefix, outgroup)
    path = prefix * ".networks"
    lines = isfile(path) ? filter(!isnothing, match.(r"^(.*;), with -loglik (\S+)", eachline(path))) : []
    newicks = isempty(lines) ? [readline(prefix * ".net")] : [m[1] for m in lines]
    for (i, newick) in enumerate(newicks)
        i > 1 && parse(Float64, lines[i][2]) == -1 && continue
        net = readnewick(newick)
        try rootatnode!(net, outgroup) catch e; e isa PhyloNetworks.RootMismatch || rethrow(); continue end
        writenewick(net, prefix * ".net")
        return write(prefix * ".choice", "$(i - 1)\n")
    end
    @warn "no candidate consistent with $outgroup; no point estimate"
    rm(prefix * ".net"; force=true)
    write(prefix * ".choice", "none\n")
end

if length(ARGS) == 3 && ARGS[1] == "--choose"
    choose(ARGS[2], ARGS[3])
    exit()
end
length(ARGS) == 7 || (println(stderr, USAGE); exit(1))
using Distributed
gtrees_path, start_path, prefix, hmax, outgroup, runs, procs = ARGS
parse(Int, procs) > 1 && addprocs(parse(Int, procs))  # one SNaQ run per worker
@everywhere using PhyloNetworks, SNaQ, DataFrames

q, t = countquartetsintrees(readmultinewick(gtrees_path); showprogressbar=false)
cfs = filter(r -> r.ngenes > 0, DataFrame(tablequartetCF(q, t); copycols=false))  # unsampled 4-taxon sets carry no CF
net = snaq!(readnewick(start_path), readtableCF(cfs);
    hmax=parse(Int, hmax), runs=parse(Int, runs), outgroup=outgroup, filename=prefix, seed=1)  # the paper's seed=0 means "from the clock"
writenewick(net, prefix * ".net")
# Rooting on OUT's edge (snaq! roots at OUT's parent, a polytomy) matches the reference.
choose(prefix, outgroup)
