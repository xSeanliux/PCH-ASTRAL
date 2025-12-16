# runid, ev_factor, polymorphism, borrowing, morph, true_tree, replica, suffix = "TEST", "2.0", "high", False, False, 2, 4, "hihp"
import beastling
from glob import glob
from beastling.configuration import Configuration
from beastling.beastxml import BeastXml
import pandas as pd
import itertools
import os
from pathlib import Path
from uuid import uuid4
import argparse 
import sys


def get_xml(
    csv_path: str,
    run_name: str,
    birth_death: bool,
):
    xml_path = Path.home() / "scratch" / f"{run_name}.xml"
    cldf_path = Path.home() / "scratch" / f"{run_name}.csv"
    # get data from simulated dataset
    df = pd.read_csv(csv_path)
    df = df.drop(
        columns = ['id', 'weight']
    ).set_index(
        'feature'
    )
    cldf_data = {
        'Language_ID': [],
        'Feature_ID': [],
        'Value': []
    }
    # convert into CLDF format
    for feature_id, taxon_states in df.iterrows():
        for taxon, state_str in taxon_states.items():
            states = state_str.split('/')
            for state in states: 
                cldf_data['Language_ID'].append(taxon)
                cldf_data['Feature_ID'].append(feature_id)
                cldf_data['Value'].append(state)
    pd_cldf = pd.DataFrame(
        data = cldf_data
    )
    pd_cldf.to_csv(cldf_path, index=False)
    # make config, change the name and the data path to point to correct CLDF file
    filename = "covarion_config.conf" if not birth_death else "covarion_config_bd.conf"
    config = Configuration(
        basename=run_name,
        configfile=
            os.getenv('TALLIS') +\
            f"/OneMostProb/scripts/beastling/{filename}"
    )
    config.admin.basename_ = run_name
    config.models[0].data = cldf_path
    beastxml = BeastXml(config)
    beastxml.write_file(filename=xml_path)

    return run_name

def main():
    parser = argparse.ArgumentParser(description="Run get_config_and_cldf_file with command-line arguments.")
    
    parser.add_argument("csv_path", type=str, help="CSV path to character state data file")
    parser.add_argument("run_name", type=str, help="unique name of beast run.")
    parser.add_argument("-d", "--birthdeath", action="store_true", help="Toggles birth death mode")
    
    args = parser.parse_args()

   
    result = get_xml(
        csv_path=args.csv_path,
        run_name=args.run_name,
        birth_death=args.birthdeath,
    )
    
    print(result)

if __name__ == "__main__":
    main()
