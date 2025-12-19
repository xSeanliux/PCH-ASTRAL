echo "Starting $0"
H_FACTORS=("0.1") # homoplasy factor
E_FACTORS=("0.8") # evolution factor
C_FACTORS=("3") # character factor

METHODS=(a)
BDFLAG=""
SETTINGS=(low)
QUARTETS=(10) 
# 10 - PCH-ASTRAL + K
# 11 - PCH-ASTRAL - K 
TIMES=3 # controls how many times a specific job is submitted.

for m in "${METHODS[@]}"; do
    for QT in "${QUARTETS[@]}"; do
        for poly in ${SETTINGS[@]}; do
            for h_factor in ${H_FACTORS[@]}; do
                for e_factor in ${E_FACTORS[@]}; do
                    for c_factor in ${C_FACTORS[@]}; do
                        NAME=$poly"_"$h_factor"_"$e_factor"_"$c_factor"_"$m"_$QT"
                        for ((i=1;i<=$TIMES;i++)); do
                            if [ $i -eq 1 ]; then 
                                RUNID=$(tr -dc A-Za-z0-9 </dev/urandom | head -c 13; echo) # random string so that runs don't use the same name (i.e. for temp files)
                                FILENAME=~/scratch/theorypaper-$NAME-simtreeinference-$RUNID.sbatch
                                echo "#!/bin/bash
#SBATCH --output=SLURM_OUT/R-%x.%j.out
#SBATCH --error=SLURM_OUT/R-%x.%j.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=4:00:00
#SBATCH --job-name=$NAME-$RUNID-treeinference
#SBATCH --partition=secondary
#SBATCH --mem=512000
source ~/.bashrc 
conda deactivate
source activate phylo
time bash run_inference_sim.sh -$m $BDFLAG -s $poly -f $e_factor  -h $h_factor -C $c_factor  -q $QT" > $FILENAME
                                LASTJOB=`sbatch $FILENAME | cut -f 4 -d " "`
                                echo $FILENAME
                                echo "submitting m=$m poly=$poly f=$e_factor hf=$h_factor cf=$c_factor QT=$QT lastjob = $LASTJOB"
                            else
                                LASTJOB=`sbatch --dependency=afterany:$LASTJOB $FILENAME | cut -f 4 -d " "`
                                echo "submitting m=$m poly=$poly f=$e_factor hf=$h_factor cf=$c_factor QT=$QT lastjob = $LASTJOB"
                            fi
                        done
                    done
                done 
            done 
        done 
    done
done
