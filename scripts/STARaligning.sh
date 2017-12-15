#!/bin/bash
#PBS -N STAR_aligning
#PBS -l nodes=1:ppn=16
#PBS -l walltime=24:00:00
#PBS -m be

#Requesting 16 nodes on delcatty, should make available 64GB RAM (-20 GB swap)

#qsub CLI env settings
#qsub -v $variables ~/scripts/qsub_scripts/STARaligning.sh

#Variables:
# NSQ_Run
# datadir
# suffix
# genome

#Set variables to commandline arguments if provided,
# otherwise they should already be provided as environmental arguments
if [ "$1" ]; then NSQ_Run=$1; fi
if [ "$2" ]; then datadir=$2; fi
if [ "$3" ]; then suffix=$3; fi
if [ "$4" ]; then genome=$4; fi
if [ "$5" ]; then pairedEnd=$5; fi

#Variable defaults
datadir="${datadir:-$VSC_DATA_VO_USER/data}"
genome="${genome:-STARgenomeGRCh38}"
pairedEnd="${pairedEnd:-False}"

#Prepare workdir
if [ "$PBS_JOBID" ]; then
    cd $TMPDIR
    if [ -d fastqs ]; then
	# if quality check ran previously on same node, fastqs will already be present
	mkdir alignmentResults
    else
	mkdir {fastqs,alignmentResults}
	cp $datadir/$NSQ_Run/*.fastq.gz fastqs/
    fi
else
    cd $datadir/../results/$NSQ_Run/
    mkdir alignmentResults
fi

for fastq in $(ls fastqs)
do
    mkdir $TMPDIR/alignmentResults/${fastq%%.*}
    if [ "$pairedEnd" = "True" ]; then
	fqfiles=$(ls fastqs/$fastq | sed 's\^\fastqs/'$fastq'/\')
	echo "Paired: " fqfiles
    else
	fqfiles=fastqs/$fastq
    fi
    STAR --runThreadN 16 --genomeDir $VSC_DATA_VO/resources/$genome \
	--readFilesIn $fqfiles \
	--readFilesCommand zcat \
	--outFileNamePrefix $TMPDIR/alignmentResults/${fastq%%.*}/ \
	--outSAMtype BAM SortedByCoordinate \
	--quantMode TranscriptomeSAM GeneCounts
done

if [ "$PBS_JOBID" ]; then
    mv $TMPDIR/alignmentResults $datadir/../results/${NSQ_Run}/alignmentResults${suffix}
fi

# Further documentation
## Previous runs
#variables=dirstructure=multidir,NSQ_Run=NSQ_Run337,forwardprob=0,qRSEM=
#variables=dirstructure=multidir_paired,NSQ_Run=neuroblast_RNAseq_Roberts
#variables=dirstructure=onedir,NSQ_Run=2015_TMPYP4_SVH,qRSEM=
#variables=dirstructure=onedir,datadir=$VSC_DATA_VO_USER/data,NSQ_Run=2015_BRIP1kd_SVH
#variables=dirstructure=multidir,datadir=$VSC_DATA_VO_USER/data,NSQ_Run=NSQ_Run212-32391392 #BRIP1kd sep2016 data
#variables=dirstructure=multidir,genome=STARzebrafish,NSQ_Run=ZF_MYCN
#variables=dirstructure=onedir,NSQ_Run=N330_ESC_17q,suffix=_mouse,genome=STARmouseGenomeGRCh38
