# PCH-ASTRAL

## Introduction 

This is the GitHub repository for the upcoming paper (under preparation). This work is a collaborative effort by the [Computational Phylogenetics in Historical Linguistics](https://tandy.cs.illinois.edu/histling.html) (CPHL) group.

This repository contains the code, data, and visualization tools that were used to generate the results and figures in the paper *Estimating Language Phylogenies from Polymorphic Characters* (under preparation). 

This work focuses on linguistic datasets, and this method is provably statistically consistent under a recently proposed polymorphic model by Canby et al. [[1]](https://tandy.cs.illinois.edu/Canby-Transactions2024.pdf). 

## Repository organisation
The top folder contains the folder `example` (under which data is put), and `scripts` (under which code is put). It also contains a `requirements.txt` for conda environment access, and multiple bash scripts to launch simulated experiments / custom data. 

File | Description 
--- | --- 
run_inference_sim.sh | Receives the model conditions and inference method as command line arguments, and performs inference of simulated data under the specified conditions and inference method. 
run_parallel_sim.sh | Launches SLURM jobs in parallel, each of which is a call to `run_inference_sim.sh`. Useful when running large-scale experiments across many conditions and methods.

### The `example` folder 
Contains all the data used for inference. Please click into the folder and read the `README` for more information. All the simulation data should be placed under `example/all_simulated_data` (create the folder first). 

### The `scripts` folder 
This folder contains code and is organised by language / function. Roughly, 
- `beastling/`: contains [BEASTLing](https://beastling.readthedocs.io/en/latest/tutorial.html) configuration files.
- `bin/`: binaries such as PAUP*.
-  `jinja/`: [Jinja](https://jinja.palletsprojects.com/en/stable/) templates for quartet parsimony (deprecated) and Stochastic Dollo. 
- `lib/`: Python functions that are called elsewhere. Importantly, ASTRAL quartet generation is in `lib/getQuartets.py`. 
- `py/`: Python command-line wrappers that call functions from `lib/` so that they can be ran with `python3 py/[SOME_FILE]`. For example, see `printQuartets.py`. 
- `pynb/`: Python notebooks used to validate data / visualise results / generate statistics. 
- `R/`: R code mostly written by Marc Canby. `R/commandLineNex.R` and `R/inferenceUtils.R` are used to generate NEXUS configuration files for MP4 and GA, `R/RFScorer.R` is used to score inference outputs, and `R/consensusTree.R` is used to generate consensus trees (as the name implies).
- `sh/`: shell scripts. The files `sh/run[METHOD].sh` runs the method of choice. The file `sh/rescore_sim.sh` is used to rescore all inference results given model condition + method for the simulated data and is called by `run_parallal_consandscore.sh`. 

## How to Run 
### Requirements 
This program requires: 
- [ASTRAL](https://github.com/smirarab/ASTRAL). Simply do 
```bash
git submodule init; git submodule update; cd ASTRAL; unzip Astral.5.7.8.zip; cd ..
```
to install ASTRAL. Your ASTRAL executable should be under `ASTRAL/Astral/astral.5.7.8.jar`.
- [ASTER](https://github.com/chaoszhang/ASTER). Similarly, do 
```bash
cd ASTER; make; cd ..
```
(assuming you've already ran `git submodule init` and `git submodule update` from the last step)
- [Java](https://www.java.com/en/). You will need to have an installation of Java to run ASTRAL. This project was developed with OpenJDK version `1.8.0_412` and runtime `1.8.0_412-b08`. 
- [PAUP*](https://paup.phylosolutions.com/), should be already under `scripts/bin/paup`. If that version for whatever reason does not work, install it and change `$PAUP_PATH` in [runMP4.sh](https://github.com/xSeanliux/PCH-ASTRAL/blob/main/scripts/sh/runMP4.sh#L32-L35).
- [MrBayes](https://nbisweden.github.io/MrBayes/), version 3.2.7. Optionally, install [BEAGLE](https://github.com/beagle-dev/beagle-lib) to speed up inference. Then please update `MB_EXEC` in [runGA.sh](https://github.com/xSeanliux/PCH-ASTRAL/blob/main/scripts/sh/runGA.sh) to point to the `mb` executable file.
- Python & [conda](https://anaconda.org/). Please install the requirements in `requirements.txt`. 
- R. Please install [R](https://www.r-project.org/). This is needed to run MP4 and transform/score the outputs of the data.

For further environment information, please refer to the [Illinois Campus Cluster Documentation](https://campuscluster.illinois.edu/resources/docs/).
### Overall Workflow 
The workflow has been optimised primarily for working in the [Illinois Campus Cluster Documentation](https://campuscluster.illinois.edu/resources/docs/). If you are working in the [CPHL Lab](DUMMY), please clone this repository under the `/projects/illinois/eng/cs/warnow/[NETID]` folder. In addition, set the environment variable `TALLIS` to `/projects/illinois/eng/cs/warnow/[NETID]` with 
```bash
echo "TALLIS=/projects/illinois/eng/cs/warnow/[NETID]" >> ~/.bashrc; source ~/.bashrc 
```
Otherwise, please set `TALLIS` to the folder containing `PCH-ASTRAL`. 
### Simulation Data
Please put your simulation data under `example/all_simulated_data`. Each replica is then under a folder with the format `{poly}_{homoplasy-factor}_{evolution-factor}_{character-factor}`. Model trees should be placed under `example/all_simulated_data/trees.txt`, and should have one tree in newick format per line, in order. For example, one replica could have the path `example/all_simulated_data/high_0_1_3/sim_tree16_1.csv`.  This means that 
- The polymorphism is high
- The homoplasy factor is 0
- The evolution factor (or tree height) is scaled by 1
- The character factor is 3, so there are 3 * 320 = 960 characters.
- The dataset was simulated down model tree 16 (i.e., the 16th line of `example/trees.txt` is the model tree), and was replica 1.
#### Launching large-scale simulations studies on the Campus Cluster using SLURM
The files in `scripts/sh` are modular and can be used to run individual inferences using a variety of methods. For the simulation data, use `run_inference_sim.sh`. The file has grown to have many configurations, but its functionality is to take in a set of model conditions and the method, and to perform inference on that model condition using the specified method. It is smart enough to detect if a tree has already been inferred and will skip that tree if it is (useful when you call it multiple times if runs pass the time limit). Its output format is as follows: it will create a folder under `sim_outputs/{MODEL_CONDITION_STRING}/{METHOD}`, where the model condition string is the same as that under `example/all_simulated_data`, and the method is the specified one. In that folder, you will see at least a folder named `trees` (where it stores the outputs) and `allscores.txt`, where it scores the output of the trees w.r.t. to the model tree.

To automate running large-scale simulation studies, use `run_parallel_sim.sh` to submit SLURM jobs to the campus cluster queue. Simply modify the first few lines (before the for loop) and the bash script will launch these jobs for you, taking the cartesian product of all variables specified. The `TIMES` variable is for when multiple jobs are required to complete one model condition (for example, `TIMES=4` means that it will let the model condition run for a maximum of 16 hours). 

#### Inference_sim arguments
The file `run_inference_sim.sh` has a lot of arguments. Here is a short explanation of what each argument/flag does. **Important note**: when you add a new model condition (esp. e/h/c factors), make sure to update it in `run_inference_sim` as it checks for if it is in a predefined list [here](https://github.com/xSeanliux/PCH-ASTRAL/blob/main/run_inference_sim.sh#L36-L60). `run_inference_sim.sh` does both inference *and* scoring. 

IMPORTANT:
- **Always** run MP4 and GA before running ASTRAL, as ASTRAL (in heuristic mode) takes all bipartitions from MP4 and GA trees.

Flag | Method 
--- | ---
-a | ASTRAL. Specify the quartet method and/or bipartition set with -q and -b, respectively. -x will set ASTRAL to run in exact mode.
-A | ASTRAL-IV. 
-c | Covarion. Specify birth-death (currently not working) with -D. 
-p | (p)arsimony, does MP4.
-g | (g)ray & atkinson, self explanatory. 
-q | Specify quartet mode. Only used if `-a` is specified. Relevant values should be 9~12, check [here](https://github.com/xSeanliux/PCH-ASTRAL/blob/main/scripts/lib/getQuartets.py#L266-L269) for a description. 
-b | Specify bipartition set. Deprecated and will always use MP4 and GA bipartition sets. MAKE SURE YOU RUN GA AND MP4 FIRST BEFORE ASTRAL!
-x | Make ASTRAL run in exact mode instead of heuristic mode.
-f | Specify evolution factor. Must be a value within the `E_FACTORS` array. 
-s | Specify polymorphism level. Must be a value within the `SETTINGS` array. 
-h | Specify homoplasy factor. Must be a value within the `H_FACTORS` array. 
-C | Specify character factor. Must be a value within the `C_FACTORS` array. 
#### Output format 
The simulation outputs will be in the folder 
```
sim_outputs/[MODEL_CONDITION]/[METHOD]
```
where `[MODEL_CONDITION]` corresponds to the folder name in `example/all_simulated_data/[MODEL_CONDITION]` and `[METHOD]` is the method name (e.g. `ASTRAL(11,5)`, `MP4`, or `GA`). Inside the folder will be at least the `trees` folder containing point estimates, and `allscores.txt`, with FN and FP scores.

The `allscores.txt` file is a simple `txt` file that has the original CSV path of the data on one line, and then the FN and FP errors on the second line, for each replicate. In other words, it is of the format 
```
[DATA CSV FILE1]
[FN1] [FP1]
[DATA CSV FILE2]
[FN2] [FP2]
...
```
**WARNING**: if the SLURM jobs fails (e.g., due to software errors or hardware errors such as out-of-memory), it is possible the list will be incomplete, or the format be missing. The plotting Python Notebook file `scripts/pynb/validation_and_plot.ipynb` tries to validate as well as it can that the required files exist and the score format is correct, but current sanity checks may not be enough. Therefore please always go into the files to check for errors if something seems off!
### I have my own data!
#### Data format
Make sure your data looks like [our data](https://github.com/xSeanliux/PCH-ASTRAL/blob/main/example/rt_2025_poly/rt_2025_poly.csv). Then use the `run_specific_dataset.sh` file, which has the same method arguments, but instead of the flags `-fshC` to indicate model conditions, there are two extra inputs: 

Flag | Meaning
--- | --- 
-i | Path to input csv file (e.g., `example/rt_2025_poly/rt_2025_poly.csv`)
-o | Folder that outputs will be put under. Defaults to the current directory `.`. The results will be put in `[OUTPUT_FOLDER]/[METHOD]` where `[OUTPUT_FOLDER]` is the argument to this option and `[METHOD]` is the inference method.
## Known Issues / Tips 
- ASTRAL-IV sometimes returns a Illegal instruction (core dumped) error. I don't know why this happens. 
- On rarer occasions I have observed MrBayes do this too. 
- ASTRAL-IV benefits from multithreading, so when launching ASTRAL-IV through `run_parallel_sim`, feel free to increase `--cpus-per-task=4` to a larger number. MP4 and ASTRAL do not seem to be able to take advantage of multithreading, though GA and SD both may be able to. 