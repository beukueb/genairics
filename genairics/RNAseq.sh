#!/usr/bin/env bash
#PBS -N RNAseqPipeline
#PBS -l nodes=1:ppn=16
#PBS -l walltime=72:00:00
#PBS -m be

module load pandas
python $VSC_DATA_VO/resources/repos/genairics/genairics/RNAseq.py --datadir $DATADIR --NSQrun $NSQRUN \
       --apitoken $APITOKEN --forwardprob $FORWARDPROB

#Not used
#--genome $GENOME
#--dirstructure $DIRSTRUCTURE --pairedEnd $pairedEnd
