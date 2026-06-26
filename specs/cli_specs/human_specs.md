## CLI Specifications 

### Inference CLI 

Akin to the simulation CLI, I would like to fill out the CLI functionality for running inference methods. In particular, there are multiple kinds of inference I would like to support. Some of them (MP, GA, PCH) are already ran through ad hoc scripts in scripts/sh/run{GA,MP4,ASTRAL}.sh, while some others are not yet implemented. 

I would like to implement a specification such that our experiments are YAML-config based, and the YAML config should serve as the source of truth for an experiment.

Thesee experiments all produce artifacts. For each method I would like to produce these artifacts _and_ an index to make sure that we can analyse these artifacts and leave a breadcrumb. For example, I would like to know the parameters of a given experiment (polymorphism level, homoplasy factor, tree height, etc.) and also the links to the artifacts that it produced (log file path, tree inference path, for methods that produce multiple trees, also the path to the list of trees in a file that it produces), maybe even metrics that we care about (FN/FP rate of the inferred tree to the true tree, runtime metrics, etc.)

Much like how simulation works, for each method I would like to have the registry in a CSV dataframe. 

### SLURM 
 
I would also like to launch these jobs through SLURM to take advantage of the compute cluster. Please look at the top level bash scripts (eg run_inference_sim.sh) to see how this currently works. The current scripts are very ad hoc and they do not scale; it is very hard to keep track of everything. 


