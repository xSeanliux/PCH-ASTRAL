## Experiments

We would like to move towards a more config-driven method of running experiments. Please see `sample_experiment/experiment_specification.yaml`. For now only the simulation of datasets according to a set of base trees & configs are supported, although we are working incorporating inference as well. 

All artifacts of the experiment will be placed in `experiment_folder`. 

### Simulation 

A sample simulation config is specified in `sample_experiment/experiment_specification.yaml` - hopefully it is self-descripting. All simulation artifacts are located under `$experiment_folder/simulation_data`. This also requires three base files from which trees & base configs are derived: 

- `base_config_dir`: a folder containing CSV files which are base configs. Base configs have the file name `$polymorphism_{,no}borrowing`. Other parameters will be derived off of that file. 
- `base_trees_file`: a file containing trees in Newick format.
- `base_networks_dir`: a directory containing networks in `net$A-$B.txt` format, where `$A` is the number of reticulation edges and `$B` is the base tree number (the `$B`-th line in `base_trees_file`). 

To run the simulation just run 

```bash
python3 -m scripts.py.cli.main simulation experiments/sample_experiment/experiment_specification.yaml
```
.