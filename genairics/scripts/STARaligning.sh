#!/bin/bash
#PBS -N STAR_aligning
#PBS -l nodes=1:ppn=16
#PBS -l walltime=24:00:00
#PBS -m be

#Requesting 16 nodes on delcatty, should make available 64GB RAM (-20 GB swap)

#qsub CLI env settings
#qsub -v $variables ~/scripts/qsub_scripts/STARaligning.sh

#Variables:
# project
# datadir
# suffix
# genome

#Set variables to commandline arguments if provided,
# otherwise they should already be provided as environmental arguments
if [ "$1" ]; then project=$1; fi
if [ "$2" ]; then datadir=$2; fi
if [ "$3" ]; then suffix=$3; fi
if [ "$4" ]; then genome=$4; fi
if [ "$5" ]; then pairedEnd=$5; fi
if [ "$6" ]; then genomedir=$6; fi

#Variable defaults
datadir="${datadir:-$VSC_DATA_VO_USER/data}"
genome="${genome:-homo_sapiens}"
pairedEnd="${pairedEnd:-False}"
genomedir="${genomedir:-$VSC_DATA_VO/resources/ensembl/homo_sapiens/release-91/transcriptome_index}"

#Prepare workdir
if [ "$PBS_JOBID" ]; then
    cd $TMPDIR
    if [ -d fastqs ]; then
	# if quality check ran previously on same node, fastqs will already be present
	mkdir alignmentResults
    else
	mkdir {fastqs,alignmentResults}
	cp $datadir/$project/*.fastq.gz fastqs/
    fi
    outdir=$TMPDIR/alignmentResults
else
    cd $datadir/../results/$project/
    mkdir alignmentResults
    outdir=$datadir/../results/$project/alignmentResults
fi

for fastq in $(ls fastqs)
do
    mkdir $outdir/${fastq%%.*}
    if [ "$pairedEnd" = "True" ]; then
	fqfiles=$(ls fastqs/$fastq | sed 's\^\fastqs/'$fastq'/\')
	echo "Paired: " fqfiles
    else
	fqfiles=fastqs/$fastq
    fi
    STAR --runThreadN 16 --genomeDir $genomedir \
	--readFilesIn $fqfiles \
	--readFilesCommand zcat \
	--outFileNamePrefix $outdir/${fastq%%.*}/ \
	--outSAMtype BAM SortedByCoordinate \
	--quantMode TranscriptomeSAM GeneCounts
done

if [ "$PBS_JOBID" ]; then
    mv $TMPDIR/alignmentResults $datadir/../results/${project}/alignmentResults${suffix}
fi

# Further documentation
## Previous runs
#variables=dirstructure=multidir,project=project337,forwardprob=0,qRSEM=
#variables=dirstructure=multidir_paired,project=neuroblast_RNAseq_Roberts
#variables=dirstructure=onedir,project=2015_TMPYP4_SVH,qRSEM=
#variables=dirstructure=onedir,datadir=$VSC_DATA_VO_USER/data,project=2015_BRIP1kd_SVH
#variables=dirstructure=multidir,datadir=$VSC_DATA_VO_USER/data,project=project212-32391392 #BRIP1kd sep2016 data
#variables=dirstructure=multidir,genome=STARzebrafish,project=ZF_MYCN
#variables=dirstructure=onedir,project=N330_ESC_17q,suffix=_mouse,genome=STARmouseGenomeGRCh38
