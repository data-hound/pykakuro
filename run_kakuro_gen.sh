#!/bin/bash
#
#SBATCH --job-name=kakuroGen                                        # Job name
#SBATCH --mem=60000                                                 # Job Memomry Request
#SBATCH -t 3-23:59                                                  # Time limit days-hrs:min:sec
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

python /hpc/group/tdunn/asabath/ece790_diffusion/Project/pykakuro/src/pykakuro/generate_dataset.py