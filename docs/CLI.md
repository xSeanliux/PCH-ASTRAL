## CLI Reference 

The CLI can be ran with 


```bash
python3 -m scripts.py.cli.main --help
```

The ultimate goal is that this CLI will be the one-stop-shop for running experiments, from generating simulation data (simulation) to inference.

### Simulation 

The `simulation` module helps with the simulation. That is, it takes a bunch of model trees (or networks) + simulation configs, and simulates datasets down it. Such datasets provide phylogenetic signal, for which we use to evaluate various inference methods on.

### Inference 

The `inference` module takes the simulation results and runs various inference methods on them. Each inference method gets their own config. In the future we will be able to orchestrate this inference using the available SLURM cluster.
