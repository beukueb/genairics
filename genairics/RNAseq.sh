#!/usr/bin/env bash
#PBS -N RNAseqPipeline
#PBS -l nodes=1:ppn=16
#PBS -l walltime=72:00:00
#PBS -m be

module load pandas
python $VSC_DATA_VO/resources/repos/genairics/genairics/RNAseq.py --datadir $DATADIR --NSQrun $NSQrun \
       --apitoken $$BASESPACE_API_TOKEN --forwardprob $FORWARDPROB

# Not used
#--genome $GENOME
#--dirstructure $DIRSTRUCTURE --pairedEnd $pairedEnd

# Example run
# qsub -v DATADIR=$VSC_DATA_VO_USER/data,NSQrun=NSQ_Run355,FORWARDPROB=0 $VSC_DATA_VO/resources/repos/genairics/genairics/RNAseq.sh
