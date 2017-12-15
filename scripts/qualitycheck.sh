#!/bin/bash
#PBS -N quality_check
#PBS -l nodes=1:ppn=4
#PBS -l walltime=72:00:00
#PBS -m be
#PBS -k oe

#qsub CLI env settings
#qsub -k oe -v $variables ~/scripts/qsub_scripts/cleaning.sh

#Variables:
# NSQ_Run
# datadir

#Previous qsub runs
#variables=dirstructure=onedir,NSQ_Run=2016_ATAC
#variables=dirstructure=multidir,NSQ_Run=neuroblast_RNAseq_Roberts

#Set variables to commandline arguments if provided,
# otherwise they should already be provided as environmental arguments
if [ "$1" ]; then NSQ_Run=$1; fi
if [ "$2" ]; then datadir=$2; fi

#Variable defaults
datadir="${datadir:-$VSC_DATA_VO_USER/data}"

# VSC modules
if [ "$VSC_HOME" ]; then
    module load fastqc
fi

#Local scratch if as PBS job
if [ "$PBS_JOBID" ]; then
    cd $TMPDIR
    mkdir fastqs
    cp $datadir/$NSQ_Run/*.fastq.gz fastqs/
    cd fastqs
else
    cd $datadir/$NSQ_Run/
fi

outdir=$datadir/../results/${NSQ_Run}/QCresults
mkdir -p $outdir

fastqc -o $outdir -t 4 *.fastq.gz
