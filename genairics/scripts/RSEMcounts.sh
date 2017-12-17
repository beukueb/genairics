#!/bin/bash
#PBS -N RSEM_counting
#PBS -l nodes=1:ppn=16
#PBS -l walltime=24:00:00
#PBS -m be

#Requesting 16 nodes on delcatty, should make available 64GB RAM (-20 GB swap)

#Run in sequence with STAR alignment
#STARJOB=$(qsub ... STARaligning.sh)
#qsub -W depend=afterok:$STARJOB RSEMcounts.sh

#qsub CLI env settings
#qsub -v $variables ~/scripts/qsub_scripts/RSEMcounts.sh

#Variables:
# project
# datadir = $VSC_DATA_VO_USER/results
# genome
# forwardprob = 0.5 -> unstranded, 0 illumina stranded
# pairedEnd = False/True -> process paired end

## Variable example runs:
#genome=STARzebrafish/zebrafish-RSEM,project=project273_ZF

#Set variables to commandline arguments if provided,
# otherwise they should already be provided as environmental arguments
if [ "$1" ]; then project=$1; fi
if [ "$2" ]; then datadir=$2; fi
if [ "$3" ]; then genome=$3; fi
if [ "$4" ]; then forwardprob=$4; fi
if [ "$5" ]; then pairedEnd=$5; fi

#Variable defaults
datadir="${datadir:-$VSC_DATA_VO_USER/data}"
genome="${genome:-$VSC_DATA_VO/resources/ensembl/homo_sapiens/release-91/transcriptome_index/homo_sapiens}"
forwardprob="${forwardprob:-0.5}"
pairedEnd="${pairedEnd:-False}"

if [ "$VSC_HOME" ]; then
    # Insure no incompatible modules are loaded
    module purge
    # Load perl for the rsem toolkit
    module load Perl;
fi

#Prepare output dirs
mkdir -p $datadir/../results/${project}/countResults
cd $datadir/../results/${project}/countResults

#Paired end option
if [ "$pairedEnd" = "True" ]; then
    PEND=--paired-end
fi

#Prepare merged fastq's
for dir in $(ls $datadir/../results/${project}/alignmentResults)
do
    if [ -d $dir.temp ]; then
        # Clean up if temporary files exist from a previous interrupted run
        rm -rf $dir.temp $dir.stat
    fi
    if [ -d $dir.stat ]; then
	# Already successfully analysed
        echo $dir processed in previous run
    else
	rsem-calculate-expression -p 16 --alignments $PEND --forward-prob $forwardprob \
				  $datadir/../results/${project}/alignmentResults/$dir/Aligned.toTranscriptome.out.bam \
				  $genome $dir
    fi
done

# Extra documentation
## RSEM
#http://deweylab.biostat.wisc.edu/rsem/rsem-calculate-expression.html
#
#--forward-prob <double> Probability of generating a read from the
#forward strand of a transcript. Set to 1 for a strand-specific
#protocol where all (upstream) reads are derived from the forward
#strand, 0 for a strand-specific protocol where all (upstream) read
#are derived from the reverse strand, or 0.5 for a non-strand-specific
#protocol. (Default: 0.5) => use 0 for illumina protocol
