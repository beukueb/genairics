#!/bin/bash
#PBS -N quality_check
#PBS -l nodes=1:ppn=4
#PBS -l walltime=72:00:00
#PBS -m be
#PBS -k oe

#qsub CLI env settings
#qsub -k oe -v $variables ~/scripts/qsub_scripts/cleaning.sh

#Variables:
# project
# datadir

#Previous qsub runs
#variables=dirstructure=onedir,project=2016_ATAC
#variables=dirstructure=multidir,project=neuroblast_RNAseq_Roberts

#Set variables to commandline arguments if provided,
# otherwise they should already be provided as environmental arguments
if [ "$1" ]; then project=$1; fi
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
    cp $datadir/$project/*.fastq.gz fastqs/
    cd fastqs
else
    cd $datadir/$project/
fi

outdir=$datadir/../results/${project}/QCresults
mkdir -p $outdir

fastqc -o $outdir -t 4 *.fastq.gz
