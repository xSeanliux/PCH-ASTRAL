# The `scripts` folder 
This folder contains code and is organised by language / function. Roughly, 
- `bin/`: binaries such as PAUP*.
- `lib/`: Python functions that are called elsewhere. Importantly, PCH quartet generation is in `lib/getQuartets.py`. 
- `py/`: Python command-line wrappers that call functions from `lib/` so that they can be ran with `python3 py/[SOME_FILE]`. For example, see `printQuartets.py`. 
- `pynb/`: Python notebooks used to validate data / visualise results / generate statistics. 
- `R/`: R code mostly written by Marc Canby. `R/commandLineNex.R` and `R/inferenceUtils.R` are used to generate NEXUS configuration files for MP4 and GA, `R/RFScorer.R` is used to score inference outputs, and `R/consensusTree.R` is used to generate consensus trees (as the name implies).
- `sh/`: shell scripts. The files `sh/run[METHOD].sh` runs the method of choice.