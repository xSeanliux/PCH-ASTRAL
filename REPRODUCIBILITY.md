# Reproducibility
## Table of Contents
<!-- TOC start (generated with https://github.com/derlin/bitdowntoc) -->

- [Reproduction](#reproduction)
   * [Table of Contents](#table-of-contents)
   * [Requirements ](#requirements)
   * [Simulation Data](#simulation-data)
   * [Launching large-scale simulations studies using SLURM](#launching-large-scale-simulations-studies-using-slurm)
      + [Inference_sim arguments](#inference_sim-arguments)
      + [Output format ](#output-format)
   * [Commands Used ](#commands-used)
      + [Commands used to run ASTRAL](#commands-used-to-run-astral)
      + [Commands used to run GA](#commands-used-to-run-ga)
      + [Commands used to run MP](#commands-used-to-run-mp)

<!-- TOC end -->

## Requirements 
This program requires: 
- [ASTRAL](https://github.com/smirarab/ASTRAL). Simply do 
```bash
git submodule update --init --recursive && pushd ASTRAL && unzip Astral.5.7.8.zip && popd
```
to install ASTRAL. Your ASTRAL executable should be under `ASTRAL/Astral/astral.5.7.8.jar`.
- [Java](https://www.java.com/en/). You will need to have an installation of Java to run ASTRAL. This project was developed with OpenJDK version `1.8.0_412` and runtime `1.8.0_412-b08`. 
- [PAUP*](https://paup.phylosolutions.com/), should be already under `scripts/bin/paup`. If that version for whatever reason does not work, install it and change `$PAUP_PATH` in [runMP4.sh](https://github.com/xSeanliux/PCH-ASTRAL/blob/main/scripts/sh/runMP4.sh#L32-L35).
- [MrBayes](https://nbisweden.github.io/MrBayes/), version 3.2.7. Optionally, install [BEAGLE](https://github.com/beagle-dev/beagle-lib) to speed up inference. Then please update `MB_EXEC` in [runGA.sh](https://github.com/xSeanliux/PCH-ASTRAL/blob/main/scripts/sh/runGA.sh#L4) to point to the `mb` executable file.
- Python & [conda](https://anaconda.org/). Please install the requirements in `requirements.txt`. 
- R. Please install [R](https://www.r-project.org/). This is needed to run MP4 and transform/score the outputs of the data.

For further environment information, please refer to the [Illinois Campus Cluster Documentation](https://campuscluster.illinois.edu/resources/docs/).

## Simulation Data
Please see `example/README.md` for information on what the naming conventions are for the folders and data under `examples/simulated_data`.

## Launching large-scale simulations studies using SLURM
The files in `scripts/sh` are modular and can be used to run individual inferences using a variety of methods. To run one setting in the simulation data, use `run_inference_sim.sh`. That file has grown to accept many configurations, but its functionality is to take in a set of model conditions and the method, and to perform inference on that model condition using the specified method. Please check the below section for an explanation on the range of arguments that `rnu_inference_sim.sh` accepts. It is smart enough to detect if a tree has already been inferred and will skip that tree if it is (useful when you call it multiple times if runs pass the time limit). Its output format is as follows: it will create a folder under `sim_outputs/{MODEL_CONDITION_STRING}/{METHOD}`, where the model condition string is the same as that under `example/simulated_data`, and the method is the specified one. In that folder, you will see at least a folder named `trees` (where it stores the outputs) and `allscores.txt`, where it scores the output of the trees w.r.t. to the model tree.

For larger datasets like the one we used, one can take advantage of the independence of datasets themselves to run these simulation studies in parallel. In our studies we submitted multiple jobs to SLURM, parameterizing runs using command line arguments using `run_parallel_sim.sh`. Simply modify the first few lines (before the for loop) and the bash script will launch these jobs for you, taking the cartesian product of all variables specified. The `TIMES` variable is for when multiple jobs are required to complete one model condition (for example, `TIMES=4` means that it will let the model condition run for a maximum of 16 hours). 

### Inference_sim arguments
The file `run_inference_sim.sh` has a lot of arguments. Here is a short explanation of what each argument/flag does. **Important note**: when you add a new model condition (esp. e/h/c factors), make sure to update it in `run_inference_sim` as it checks for if it is in a predefined list [here](https://github.com/xSeanliux/PCH-ASTRAL/blob/main/run_inference_sim.sh#L36-L60). `run_inference_sim.sh` does both inference *and* scoring. 

IMPORTANT:
- **Always** run MP4 and GA before running ASTRAL, as ASTRAL (in heuristic mode) takes all bipartitions from MP4 and GA trees.

Flag | Method 
--- | ---
-a | ASTRAL. Specify the quartet method and/or bipartition set with -q and -b, respectively. -x will set ASTRAL to run in exact mode.
-p | (p)arsimony, does MP.
-g | (g)ray & atkinson, self explanatory. 
-q | Specify quartet mode. Only used if `-a` is specified. Relevant values should be either 10 or 11, check [here](https://github.com/xSeanliux/PCH-ASTRAL/blob/main/scripts/lib/getQuartets.py#L164-L168) for a description. 
-b | Specify bipartition set. Deprecated and will always use MP4 and GA bipartition sets. **MAKE SURE YOU RUN GA AND MP4 FIRST BEFORE ASTRAL!**
-x | Make ASTRAL run in exact mode instead of heuristic mode.
-f | Specify evolution factor. Must be a value within the `E_FACTORS` array. This is a scalar time multiplicative factor applied onto all characters, and is fixed at 0.8 for this studiy.
-s | Specify polymorphism level. Must be a value within the `SETTINGS` array. It can take on one of three values: `no`, `low`, `high`. 
-h | Specify homoplasy factor. Must be a value within the `H_FACTORS` array. This is $h$ and $h_{root}$ in Warnow et al.'s 2006 model [[2]](https://www.stat.berkeley.edu/users/evans/673.pdf).
-C | Specify character factor. Must be a value within the `C_FACTORS` array. This controls how many characters to simulate down; the actual number of characters is this factor multiplied by 320.
### Output format 
The simulation outputs will be in the folder 
```
sim_outputs/[MODEL_CONDITION]/[METHOD]
```
where `[MODEL_CONDITION]` corresponds to the folder name in `example/simulated_data/[MODEL_CONDITION]` and `[METHOD]` is the method name (e.g. `ASTRAL(11,5)`, `MP4`, or `GA`). Inside the folder will be at least the `trees` folder containing point estimates, and `allscores.txt`, with FN and FP scores.

The `allscores.txt` file is a simple `txt` file that has the original CSV path of the data on one line, and then the FN and FP errors on the second line, for each replicate. In other words, it is of the format 
```
[DATA CSV FILE1]
[FN1] [FP1]
[DATA CSV FILE2]
[FN2] [FP2]
...
```
**WARNING**: if the SLURM jobs fails (e.g., due to software errors or hardware errors such as out-of-memory), it is possible the list will be incomplete, or the format be missing. The plotting Python Notebook file `scripts/pynb/validation_and_plot.ipynb` tries to validate as well as it can that the required files exist and the score format is correct, but current sanity checks may not be enough. Therefore please always go into the files to check for errors if something seems off!

## Commands Used 

### Commands used to run ASTRAL

We take the latest version of ASTRAL-III from its
GitHub site. We used ASTRAL 5.7.8. Additionally, we also fed into ASTRAL the set of
bipartitions of all MP trees and all GA trees. The code to generate this set of bipartitions can be found at `scripts/py/printBipartitions.py`. 

We refer the reader to the [`scripts/sh/runASTRAL.sh` bash
file](https://github.com/xSeanliux/PCH-ASTRAL/blob/main/scripts/sh/runASTRAL.sh)
for example usage, and to the [ASTRAL repository](https://github.com/smirarab/ASTRAL) for an
in-depth tutorial and explanation of advanced features within ASTRAL.

### Commands used to run GA

See the [`runGA.sh` bash
file](https://github.com/xSeanliux/PCH-ASTRAL/blob/main/scripts/sh/runGA.sh)
in the PCH-ASTRAL repository for example usage.

We use MrBayes 3.2.7 x86_64 to run GA. To prepare the input Nexus file
for submission to MrBayes, you will need
`commandLineNexus.R` from `scripts/R/commandLineNex.R`.

As GA will output trees at regular iteration intervals, we discard the
first $50\%$ of trees and then take the MCC tree of the remaining trees.

### Commands used to run MP

See the [`runMP.sh` bash
file](https://github.com/xSeanliux/PCH-ASTRAL/blob/main/scripts/sh/runMP4.sh)
in the PCH-ASTRAL repository for example usage.

We use PAUP* v. 4.0a (build 168) for Unix/Linux. To prepare the input
Nexus file for use by PAUP\*, we use the same
[`commandLineNex.R`](https://github.com/xSeanliux/PCH-ASTRAL/blob/main/scripts/R/commandLineNex.R)
from the PCH-ASTRAL repository mentioned above.

As MP can output many trees, we take the majority consensus of these
trees as our point estimate.
