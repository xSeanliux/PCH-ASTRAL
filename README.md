# PCH-ASTRAL (Polymorphic CHaracters with ASTRAL)
## Table of Contents 
<!-- TOC start (generated with https://github.com/derlin/bitdowntoc) -->

- [PCH-ASTRAL (Polymorphic CHaracters with ASTRAL)](#pch-astral-polymorphic-characters-with-astral)
   * [Table of Contents](#table-of-contents)
   * [Introduction ](#introduction)
   * [Repository organization](#repository-organization)
      + [The `data` folder ](#the-example-folder)
      + [The `scripts` folder ](#the-scripts-folder)
   * [Reproduction](#reproduction)
   * [Running on your own data](#running-on-your-own-data)
      + [Data format](#data-format)
   * [References ](#references)

<!-- TOC end -->


## Introduction 

This work is a collaborative effort by the [Computational Phylogenetics in Historical Linguistics](https://tandy.cs.illinois.edu/histling.html) (CPHL) group. This repository contains the code, data, and visualization tools that were used to generate the results and figures in the paper *Estimating Language Phylogenies from Polymorphic Characters* (in preparation).

This work focuses on linguistic datasets, and this method is provably statistically consistent under a recently proposed polymorphic model by Canby et al. [[1]](https://tandy.cs.illinois.edu/Canby-Transactions2024.pdf). 

The method addressed here is the inference of linguistic phylogenies given a set of polymorphic traits (characters). These characters are given in tabular form and assumed to have evolved under the Canby et al. model. The method we present, PCH-ASTRAL, takes a multistep approach:
1. Perform inference using a variant of maximum parsimony (MP4 in Canby et al.) and a Bayesian method (following Gray & Atkinson, 2003 [[3]](https://scholar.google.com/scholar_url?url=https://www.nature.com/articles/nature02029&hl=en&sa=T&oi=gsb&ct=res&cd=2&d=8425091542861310623&ei=PuJJaezAFrPFieoPper8uAM&scisig=ALhkC2RkqXHmcQzi4dDJyKXKhUy7)). This gives us a set of tree estimates. 
2. From the data we generate a multiset of quartet trees, that is, unrooted four-leaf binary trees, on the binary tree.
3. Run ASTRAL on the aforementioned set of quartet trees, using the trees in Step 1 to augment the search space. This finds the unrooted tree that has the highest quartet compatibility score of all trees, subject to drawing its bipartition from the constraint set and its own bipartition generation heuristics.

For detailed information on how to reproduce the results we obtained in the paper, please see [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md).

## Repository organization
The top folder contains the folder `data/` (under which data is put), and `scripts` (under which code is put). It also contains a `requirements.txt` for conda environment access, and multiple bash scripts to launch simulated experiments / custom data. 

File | Description 
--- | --- 
`run_inference_sim.sh` | Receives the model conditions and inference method as command line arguments, and performs inference of simulated data under the specified conditions and inference method. 
`run_parallel_sim.sh` | Launches SLURM jobs in parallel, each of which is a call to `run_inference_sim.sh`. Useful when running large-scale experiments across many conditions and methods.
`run_specific_dataset.sh` | Useful for launching a run on a single dataset.

**NOTE:** As ASTRAL requires Maximum Parsimony (MP) and Gray & Atkinson (GA) trees to be present (to augment the constraint space), make sure that MP and GA have ran first before running ASTRAL. 

### The `data/` folder 
Contains both the simulation and IE data used in our paper. Please click into the folder and read the `README` for more information.

### The `scripts` folder 
This folder contains code and is organised by language / function. Please read the `README` in the folder for more information.

## Reproducibility
For a full reproducibility tutorial, please see [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md). 

## Running on your own data
### Data format
Make sure your data looks like [our data](https://github.com/xSeanliux/PCH-ASTRAL/blob/main/data/rt_2025_poly_screened_lv_1.csv). Then use the `run_specific_dataset.sh` file, which has the same method arguments, but instead of the flags `-fshC` to indicate model conditions, there are two extra inputs: 

Flag | Meaning
--- | --- 
-i | Path to input csv file (e.g., `data/rt_2025_poly_screened_lv_1.csv`)
-o | Folder that outputs will be put under. Defaults to the current directory `.`. The results will be put in `[OUTPUT_FOLDER]/[METHOD]` where `[OUTPUT_FOLDER]` is the argument to this option and `[METHOD]` is the inference method.

See [here](REPRODUCIBILITY.md#inference_sim-arguments) for a comprehensive summary of the arguments to `run_specific_dataset.sh`. For example, one could run 
```bash
$ bash run_specific_dataset.sh -i $YOUR_DATA_FILE -pg
```
to perform inference on `$YOUR_DATA_FILE` using MP (`p`) and GA (`g`). Then they could do 
```bash
$ bash run_specific_dataset.sh -i $YOUR_DATA_FILE -a
```
to perform inference using PCH-ASTRAL-K.
## References 
1. [Canby, Marc E., et al. "Addressing polymorphism in linguistic phylogenetics." Transactions of the Philological Society 122.2 (2024): 191-222.](https://tandy.cs.illinois.edu/Canby-Transactions2024.pdf)
2. [Warnow, Tandy, et al. "A stochastic model of language evolution that incorporates homoplasy and borrowing." Phylogenetic methods and the prehistory of languages (2006): 75-90.](http://www.cs.rice.edu/~nakhleh/Papers/WarnowRevComplete.pdf)
3. [Gray, Russell D., and Quentin D. Atkinson. "Language-tree divergence times support the Anatolian theory of Indo-European origin." Nature 426.6965 (2003): 435-439.](https://scholar.google.com/scholar_url?url=https://www.nature.com/articles/nature02029&hl=en&sa=T&oi=gsb&ct=res&cd=2&d=8425091542861310623&ei=PuJJaezAFrPFieoPper8uAM&scisig=ALhkC2RkqXHmcQzi4dDJyKXKhUy7)