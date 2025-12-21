# The `data/` folder
This folder contains all the data used in our simulation studies and our Indo-European analysis. 

### Simulation Data
The simulation data is composed of three parts: 
- The configuration files used to generate the simulation data (under `configs/`),
- The model trees (one per line in `trees.txt`), and
- The simulated character data themselves (in `simulated_data`).

The character data was simulated using [LingPhyloSimulator](https://github.com/marccanby/LingPhyloSimulator/). The seed used for each 

Each replica is under a folder with format `{poly}_{homoplasy-factor}_{evolution-factor}_{character-factor}`. Model trees should be placed under `data/simulated_data/trees.txt`, and should have one tree in newick format per line, in order. For example, one replica could have the path `data/simulated_data/high_0.1_0.8_0.5/sim_tree16_1.csv`.  This means that 
- The polymorphism is high
- The homoplasy factor is 0.1
- The evolution factor (or tree height) is scaled by 0.8.
- The character factor is 3, so there are 0.5 * 320 = 160 characters.
- The dataset was simulated down model tree 16 (i.e., the 16th line of `trees.txt` is the model tree), and was replica 1.

### Indo-European Data 
All our Indo-European data can be found in `rt_2025_poly/`. In the paper we used `rt_2025_poly_screened_lv_1.csv` as our target dataset as it was the dataset which filtered out most cases of obvious homoplasy. The full dataset, other screening levels, and their explanations are also in the folder.