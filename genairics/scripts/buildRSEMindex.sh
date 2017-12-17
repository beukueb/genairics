#!/bin/bash
#PBS -N build_RSEM_index
#PBS -l nodes=1:ppn=16
#PBS -l walltime=24:00:00
#PBS -m be

#Requesting 16 nodes on delcatty, should make available 64GB RAM (-20 GB swap)

if [ "$1" ]; then GTF_FILE=$1; fi
if [ "$2" ]; then THREADS=$2; fi
if [ "$3" ]; then FAFILES=$3; fi
if [ "$4" ]; then INDEXPATH=$4; fi

if [ "$VSC_HOME" ]; then
    # Insure no incompatible modules are loaded
    module purge
    # Load perl for the rsem toolkit
    module load Perl;
fi

rsem-prepare-reference --gtf $GTF_FILE --star --star-sjdboverhang 100 -p $THREADS \
		       $FAFILES $INDEXPATH
