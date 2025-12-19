# PCH-ASTRAL (Polymorphic CHaracters with ASTRAL)

## Introduction 

This is the GitHub repository for the upcoming paper (under preparation). This work is a collaborative effort by the [Computational Phylogenetics in Historical Linguistics](https://tandy.cs.illinois.edu/histling.html) (CPHL) group.

This repository contains the code, data, and visualization tools that were used to generate the results and figures in the paper *Estimating Language Phylogenies from Polymorphic Characters* (under preparation).

This work focuses on linguistic datasets, and this method is provably statistically consistent under a recently proposed polymorphic model by Canby et al. [[1]](https://tandy.cs.illinois.edu/Canby-Transactions2024.pdf). 

## Repository organization
The top folder contains the folder `example` (under which data is put), and `scripts` (under which code is put). It also contains a `requirements.txt` for conda environment access, and multiple bash scripts to launch simulated experiments / custom data. 

File | Description 
--- | --- 
`run_inference_sim.sh` | Receives the model conditions and inference method as command line arguments, and performs inference of simulated data under the specified conditions and inference method. 
`run_parallel_sim.sh` | Launches SLURM jobs in parallel, each of which is a call to `run_inference_sim.sh`. Useful when running large-scale experiments across many conditions and methods.
`run_specific_dataset.sh` | Useful for launching a run on a single dataset.

**NOTE:** As ASTRAL requires MP and GA trees to be present (to augment the constraint space), make sure that MP and GA have ran first before running ASTRAL. 

### The `example` folder 
Contains all the data used for inference. Please click into the folder and read the `README` for more information.

### The `scripts` folder 
This folder contains code and is organised by language / function. Please read the `README` in the folder for more information.

## Reproduction
For a full reproduction tutorial, please see `REPRODUCIBILITY.md`. 

## Running on your own data
### Data format
Make sure your data looks like [our data](https://github.com/xSeanliux/PCH-ASTRAL/blob/main/example/rt_2025_poly/rt_2025_poly.csv). Then use the `run_specific_dataset.sh` file, which has the same method arguments, but instead of the flags `-fshC` to indicate model conditions, there are two extra inputs: 

Flag | Meaning
--- | --- 
-i | Path to input csv file (e.g., `example/rt_2025_poly/rt_2025_poly.csv`)
-o | Folder that outputs will be put under. Defaults to the current directory `.`. The results will be put in `[OUTPUT_FOLDER]/[METHOD]` where `[OUTPUT_FOLDER]` is the argument to this option and `[METHOD]` is the inference method.

## References 
1. Canby, Marc E., et al. "Addressing polymorphism in linguistic phylogenetics." Transactions of the Philological Society 122.2 (2024): 191-222.
2. Warnow, Tandy, et al. "A stochastic model of language evolution that incorporates homoplasy and borrowing." Phylogenetic methods and the prehistory of languages (2006): 75-90.