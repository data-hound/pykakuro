#!/bin/bash
#
#SBATCH --job-name=kakuroGen                                        # Job name
#SBATCH --mem=60000                                                 # Job Memomry Request
#SBATCH -t 1-00:59                                                  # Time limit days-hrs:min:sec
#SBATCH -N 1                                                        # Requested number of nodes (usually just 1)
#SBATCH -n 12                                                       # Requested number of CPUS
#SBATCH -p common              # Requested Partition on which the job will be run
#SBATCH --output=logs/%j.out
#SBATCH --error=logs/%j.err



set +e
source ~/.bashrc
# module load Anaconda3/5.1.0
# source activate diffusion_lang              # dannce is the name of conda env
conda activate diffusion_lang
source /hpc/group/tdunn/as1296/miniconda3/etc/profile.d/conda.sh

cd /hpc/group/tdunn/asabath/ece790_diffusion/Project/pykakuro

echo "HOSTNAME=$HOSTNAME"
echo "SHELL=$SHELL"
echo "PATH=$PATH"
which conda || true
which python || true
conda info --envs || true
python -V || true
echo "Using python: $(which python)"

python /hpc/group/tdunn/asabath/ece790_diffusion/Project/pykakuro/src/pykakuro/generate_dataset.py --board_size 9 --start_id 100000 --puzzle_count 250000
wait
echo "Starting for boardsize 11"
python /hpc/group/tdunn/asabath/ece790_diffusion/Project/pykakuro/src/pykakuro/generate_dataset.py --board_size 11 --start_id 100000 --puzzle_count 250000
wait
echo "Starting for boardsize 15"
python /hpc/group/tdunn/asabath/ece790_diffusion/Project/pykakuro/src/pykakuro/generate_dataset.py --board_size 15 --start_id 100000 --puzzle_count 250000
wait
echo "Finished all generations"


