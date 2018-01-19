#!/usr/bin/env python
"""
ChIP sequencing pipeline starting from BaseSpace fastq project
"""
from datetime import datetime, timedelta
import luigi, os, tempfile, pathlib, glob
from luigi.contrib.external_program import ExternalProgramTask
from luigi.util import inherits, requires
from plumbum import local, colors
import pandas as pd
import logging

## Tasks
from genairics import config, logger, gscripts, setupProject
from genairics.datasources import BaseSpaceSource, mergeFASTQs
from genairics.resources import resourcedir, STARandRSEMindex, RetrieveBlacklist
from genairics.RNAseq import qualityCheck

### ChIP specific Task
class cutadapt(luigi.Config):
    """
    Info: http://cutadapt.readthedocs.io/en/stable/guide.html
    """
    adapter = luigi.Parameter(
        default = "GATCGGAAGAGCACACGTCTGAACTCCAGTCACCGATGTATCTCGTATGC",
        description = "cutadapt adapter to trim"
    )
    errorRate = luigi.FloatParameter(
        default = 0.1,
        description = "allowed error rate => errors #/length mapping"
    )

@inherits(cutadapt)
class TrimFilterSample(luigi.Task):
    infile = luigi.Parameter()
    outfile = luigi.Parameter()
    
    def run(self):
        stdout = local['cutadapt'](
            '--cores', config.threads,
            '-a', self.adapter,
            '-e', self.errorRate,
            '-o', self.outfile,
            self.infile
        )
        if stdout: logger(stdout)

#subsampleTask => subsampling naar 30 miljoen indien meer

#class mapSample
#bowtie2 lopen en output doorspelen naar samtools, filer mapQ #groter dan 4
#input SAM, output BAM, include header
#bowtie2 -p 4 -x /Shared/references/Hsapiens/hg19/hg19full/bowtie2_index/hg19full -U $list_R1 | samtools view -q 4 -Sbh - > ${PBS_ARRAYID}.bam
#bowtie2 -p 4 -x /Shared/references/hg38/hg38full/bowtie2_index/hg38full -U $list_R1 | samtools view -q 4 -Sbh - > ${PBS_ARRAYID}_hg38.bam

#output sorteren
#samtools sort ${PBS_ARRAYID}.bam -o ${PBS_ARRAYID}_sorted.bam
#samtools sort ${PBS_ARRAYID}_hg38.bam -o ${PBS_ARRAYID}_hg38_sorted.bam

#indexeren
#samtools index ${PBS_ARRAYID}_sorted.bam
#samtools index ${PBS_ARRAYID}_hg38_sorted.bam

#niet gesorteerde BAM file wissen
#rm ${PBS_ARRAYID}.bam
#rm ${PBS_ARRAYID}_hg38.bam

#run samstat on the bamfile
#/home/projects/ChIP-seq_oncogenes_neuroblastoma/tools/samstat/src/samstat ${bm}
#echo ${bm} >> /home/bdcaeste/fastqfiles/flagstatsummary.txt
#samtools flagstat ${bm} >> /home/bdcaeste/fastqfiles/flagstatsummary.txt;
#done

#macs2 callpeak -t ../../NSQ_Run335/sam_2/CLBGA_TBX2_all_clean_sorted_MAPQ4.bam -c ../../NSQ_Run335/sam_1/CLBGA_INPUT_all_clean_sorted_MAPQ4.bam --outdir TBX2_vs_input_G_CLBGA_macs2_hg19_mapq4/ -n diff_peaks_TBX2_G_CLBGA -q 0.05 -g hs --bdg

#Rscript –vanilla diff_peaks_SOX11_D_NGP.r

#make igv file

#for bm in sam*/*.bam;do
#name=${bm##/}
#prefix=${name%%.bam}
#echo ${prefix}
#igvtools count ${bm} ${prefix}.tdf /Shared/Software/share/igvtools-2.3.93-0/genomes/hg19.chrom.sizes
#echo "Completed";
#done

#HOMER
#PATH=$PATH:/home/bdcaeste/tools/Homer/.//bin/
#makeTagDirectory CLBGA_TBX2_Run335/ ../../NSQ_Run335/sam_2/CLBGA_TBX2_G_all_clean_sorted_MAPQ4.bam
#findPeaks IMR32_TBX2/ -style factor -o TBX2_vs_Input_1_IMR32_homer/TBX2_vs_Input_IMR32 -i IMR32_INPUT/
#pos2bed.pl TBX2_vs_Input_IMR32 > TBX2_vs_Input_IMR32_AC.bed

#DeepTools for clustering of bam files
#multiBamSummary bins --bamfiles sam_1/CLBGA_INPUT_F_sorted.bam sam_2/CLBGA_TBX2_F_sorted.bam sam_6/SKNAS_INPUT_B_sorted.bam sam_7/SKNAS_TBX2_B_sorted.bam sam_8/SKNAS_H3K27ac_B_sorted.bam -out multiBamSummary_bam_Run296.npz --labels CLBGA_INPUT CLBGA_TBX2 SKNAS_INPUT SKNAS_TBX2 SKNAS_H3K27ac
#plotCorrelation --corData multiBamSummary_bam_Run296.npz --plotFile correlation_peaks.pdf --outFileCorMatrix correlation_peaks_matrix.txt --whatToPlot heatmap --corMethod pearson --plotNumbers --removeOutliers
