# Join Keys 

The main join keys of this dataset are: 

1. dataset key: they uniquely determine the _tree/network_ from which to simulate things down: 
    - tree number (int)
    - number of lateral transfer / reticulate edges (int), 0 means tree and >= 1 means network. 

2. Simulation config key: uniquely determines _what_ the  configuration is for characters to be simulated down the tree:
    - polymorphism level: (in `verylow`, `low`, `mid`, `high`, `veryhigh`)
    - min tree height (int) 
    - homoplasy factor (float) 
    - no. characters 

3. Dataset config key: uniquely determines each _dataset_ that is used, and each maps to a single CSV file.
    - dataset key 
    - simulation config key 
    - replicate number (int), we use multiple replicates per dataset key & sim config key to reduce variance. 


4. Inference methods: 
    - PCH_W: is a method of getting quartets from a dataset CSV file. We then use a number of _quartet summary methods_ to find the tree maximising satisfied quartets — an NP-hard problem, so each summary method approximates it differently:
        - ASTRAL III: Java, dynamic programming over a constrained set of bipartitions drawn from the input quartets; statistically consistent under the multi-species coalescent. Accepts manual bipartition enhancement sets on top of the automatic ones. (Zhang et al. 2018, BMC Bioinformatics.)
        - ASTRAL IV: C++ reimplementation in the ASTER package. Builds its own search space via greedy placement + NNI refinement, so no manual bipartition set is needed; scales near-linearly in the number of quartets. (Zhang et al. 2025, MBE.)
        - wASTRAL: weighted ASTRAL (ASTER). Each quartet contributes a weight (by gene-tree branch support and/or length) rather than a unit vote, folding quartet uncertainty into the objective. Identical quartets are collapsed and their weights summed, so runtime scales with the number of _unique_ quartets, not the raw count. (Zhang & Mirarab 2022, MBE.)
        - Tree weighted QMC (TREE-QMC): divide-and-conquer on the Quartet Max Cut framework — builds a taxon graph weighted by quartet agreement, takes a max cut to bipartition, and recurses. Offers several quartet normalisation schemes (n0/n1/n2) to correct weight inflation from artificial taxa. (Yan et al. 2023, Genome Research.)
    - Gray & Atkinson: Bayesian inference over cognate presence/absence characters. Uses MrBayes (MCMC) to sample trees from a posterior distribution, then takes the MCC (maximum clade credibility) tree — the sampled tree maximising the product of its clades' posterior probabilities — as the point estimate. (Gray & Atkinson 2003, Nature.)
    - Maximum Parsimony (MP, MP4): finds the tree(s) minimising total character-state changes. Ties are common, so the majority consensus of the equally-parsimonious trees is the point estimate. MP4 is the best-performing of the MP variants for polymorphic characters in Canby et al. 2024 (Trans. Philological Society). 
    
