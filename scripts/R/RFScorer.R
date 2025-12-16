 

library(optparse, warn.conflicts = FALSE, quietly = TRUE)
library(dplyr, warn.conflicts = FALSE, quietly = TRUE)
library(stringr, warn.conflicts = FALSE, quietly = TRUE)
library(ape, warn.conflicts = FALSE, quietly = TRUE)
library(testit, warn.conflicts = FALSE, quietly = TRUE)
library(phangorn, warn.conflicts = FALSE, quietly = TRUE)
library(castor, warn.conflicts = FALSE, quietly = TRUE)
library(TreeDist, warn.conflicts = FALSE, quietly = TRUE)

option_list = list(
  make_option(c("-i", "--input-trees"), type="character", default=NULL,
              help="input trees file name", metavar="character"),
  make_option(c("-f", "--format"), type="character", default="nexus",
              help="input tree(s) file format, nexus for NEXUS; newick for Newick.", metavar="str"),
  make_option(c("-r", "--reference-tree", type='character', default=NULL,
                help='output file for score', metavar='character')),
  make_option(c("-m", "--resolve-multiple"), type="integer", default=NULL,
              help="How to resolve multiple trees (1=average, 2=majority consensus, 3=MAP, 4=MCC)", metavar="character"),
  make_option(c("-p", "--do-print", type='character', default='0',
                help='whether or not to print progress (0 or 1)', metavar='character')),
  make_option(c("-x", "--prune", type='character', default="",
                help='the name of a leaf to prune before scoring (usually the extra root indicator)', metavar='character'))

);

opt_parser = OptionParser(option_list=option_list);
opt = parse_args(opt_parser);

for (x in unlist(lapply(option_list, function(x) slot(x, 'long_flag')))) {
  if (x == '--do-print') next
  if (x == '--prune') next
  assert (paste0(substr(x, 2, nchar(x)), ' cannot be null'), {!is.null(opt[[substr(x, 3, nchar(x))]])})
}

format = opt[['format']]
assert({format %in% c('nexus', 'newick')})

getTreesFromFile <- function(file) {
  # print(c("Prune is <", opt[["prune"]], ">", (opt[['prune']] == NULL)))
  if(format == 'nexus') {
    trees = read.nexus(file, tree.names = NULL, force.multi = TRUE)
  } else if (format == 'newick') {
    trees = read.tree(file, tree.names = NULL, keep.multi = TRUE)
  }
   
  for (i in 1:length(trees)) {
    # print(c("Tree is null?", is.null(trees[[i]])))
    if(!is.null(opt[['prune']])) {
      trees[[i]] = drop.tip(trees[[i]], opt[['prune']])
    }
    if (is.rooted(trees[[i]])) trees[[i]] = unroot(trees[[i]])
  }
  for (i in 1:length(trees)) assert({!is.rooted(trees[[i]])})
  trees # May be multiple!!!
}

computeFnFpRate <- function(tree, ref_tree) {
  assert({!is.rooted(tree) && !is.rooted(ref_tree)})
  N = length(tree$tip.label)
  assert({N == length(ref_tree$tip.label)}) # Same number of leaves
  assert({ref_tree$Nnode == N - 2}) # Ref tree must be binary

  splits1 = as.matrix(removeTrivialSplits(as.splits(tree)))
  splits2 = as.matrix(removeTrivialSplits(as.splits(ref_tree)))
  cnames1 = colnames(splits1)
  splits2 = splits2[,cnames1] # Make sure columns in same order!

  splits1_ = apply(splits1, 1, paste0, collapse='')
  splits2_ = apply(splits2, 1, paste0, collapse='')
  fn_list =c()
  fp_list =c()
  is_partition_is_in_lst <- function(cand, splts) { # Idea of this is that 10001 == 01110 (could be coded opposite)
    cand_bool <- as.logical(as.integer(str_split(cand, '')[[1]]))
    for (s in splts) {
      s_bool <- as.logical(as.integer(str_split(s, '')[[1]]))
      xr <- xor(cand_bool, s_bool)
      if (all(xr) || all(!xr)) return (TRUE)
    }
    return (FALSE)
  }
  for (s in splits1_) if (!is_partition_is_in_lst(s, splits2_)) fp_list <- c(fp_list, s)
  for (s in splits2_) if (!is_partition_is_in_lst(s, splits1_)) fn_list <- c(fn_list, s)

  rf = RobinsonFoulds(tree, ref_tree)
  fp = length(fp_list)
  fn = length(fn_list)
  assert({fn <= N-3 && fp <= N-3})
  if ({tree$Nnode == N - 2}) assert({fp == fn})
  assert({fp + fn == rf})
  # print(c("fn is", fn/(N -3), " for ", write.tree(tree), write.tree(ref_tree)))
  # print(class(tree))
  c(fn/(N-3),fp/(N-3))
}

calculateMapTree <- function (trees, do_print=FALSE) {
  assert({length(trees) > 100}) # doesnt really matter but just to make sure not feeding it 1 tree or something
  counts = list()
  for (i in 1:length(trees)) {
    if (do_print && i %% 50 == 0) print(i)
    tree_i = trees[[i]]
    assert(!is.rooted(tree_i))
    found_tree=FALSE
    for (j in names(counts)) {
      tree_j = trees[[as.integer(j)]]
      is_equal = all.equal(tree_i, tree_j, use.edge.length =FALSE)
      if (is_equal) {
        counts[[j]] = counts[[j]] + 1
        found_tree = TRUE
        break
      }
    }
    if (!found_tree) {
      counts[[as.character(i)]] = 1
    }
  }
  mx_cnt = 0
  mx_arg = NULL
  for (j in names(counts)) {
    if (counts[[j]] > mx_cnt) {
      mx_cnt = counts[[j]]
      mx_arg = list(j = trees[[as.integer(j)]])
    }
    else if (counts[[j]] == mx_cnt) {
      mx_arg[[j]] = trees[[as.integer(j)]] # Add it in
    }
  }
  mx_arg
}

makeConsensusTrees <- function(trees) {
  strict <- consensus(trees$trees, p=1, check.labels=TRUE, rooted=FALSE)
  majority <- consensus(trees$trees, p=0.5, check.labels=TRUE, rooted=FALSE)
  strict$node.label = NULL
  majority$node.label = NULL
  nms <- c('Strict Consensus', 'Majority Consensus')
  list(trees=list(strict, majority), names=nms)
}


resolve_multiple = opt[['resolve-multiple']]
inpfil = opt[['input-trees']]
ref_newick = opt[['reference-tree']]
do_print = opt[['do-print']]

assert({resolve_multiple %in% 1:4})
assert({do_print %in% c('0', '1')})

ref_tree <- unroot(ape::read.tree(text=ref_newick))
trees <- getTreesFromFile(inpfil)

returnTreeSetForMultiple <- function(trees, method) {

  if (method == 1) return(trees) # Avg
  else if (method == 3) return(calculateMapTree(trees)) # MAP
  else if (method == 4) { # MCC
    res = maxCladeCred(trees, rooted = FALSE)
    trees = list()
    trees[[1]] = res
    return(trees)
  }
  else if (method == 2) { # Maj Con
    cons = makeConsensusTrees(list(trees=trees))
    assert({cons$names[2] == 'Majority Consensus'})
    tree = cons$trees[2]
    return(tree)
  }
  else stop("Invalid method!")
}

if (length(trees) > 1) trees <- returnTreeSetForMultiple(trees, resolve_multiple)

fn_rates = c()
fp_rates = c()
for (i in 1:length(trees)) {
  if (i %% 100 == 0 && do_print == '1') print(i)
  tree=trees[[i]]
  score <- computeFnFpRate(tree, ref_tree)
  fn_rates <- c(fn_rates, score[1])
  fp_rates <- c(fp_rates, score[2])
}
fn_rate <- sum(fn_rates) / length(fn_rates)
fp_rate <- sum(fp_rates) / length(fp_rates)

cat(paste0(fn_rate, ' ', fp_rate, '\n'))


