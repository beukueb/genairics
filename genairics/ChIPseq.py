#!/usr/bin/env python
"""
Full pipeline starting from BaseSpace fastq project
"""
from datetime import datetime, timedelta
import luigi, os, tempfile, pathlib, glob
from luigi.contrib.external_program import ExternalProgramTask
from luigi.util import inherits
from plumbum import local, colors
import pandas as pd
import logging

# matplotlib => setup for exporting svg figures only
import matplotlib
matplotlib.use('SVG')
import matplotlib.pyplot as plt

## Tasks
from genairics import setupProject, setupLogging
from genairics.RNAseq import mergeFASTQs

### Single file tasks
class Sample(luigi.Task):
    """
    This class simply describes the parameters needed to work with a sample.
    When inherited tasks can process a sample.
    """
    sample = luigi.Parameter(description="sample filename")
    resultdir = luigi.Parameter(description="general result directory")
    extension = luigi.ChoiceParameter(choices=['fastq','fastq.gz'],default='fastq.gz')

    @property
    def name(self):
        return os.path.basename(self.sample)[:-1-len(self.extension)]
        
    def output(self):
        return {
            'sample': luigi.LocalTarget(self.sample),
            'resultdir': luigi.LocalTarget(self.resultdir),
            'sampleresults': luigi.LocalTarget('{}/{}'.format(self.resultdir,self.name))
        }

    def run(self):
        logger = logging.getLogger(__package__)
        if not self.output()['resultdir'].exists():
            os.mkdir(self.output()['resultdir'].path)
            logger.info('created result directory %s',self.output()['resultdir'].path)
        if not self.output()['sample'].exists():
            logger.error('sample "%s" not found',self.output()['sample'].path)
            raise FileNotFoundError
        if not self.sample.endswith(self.extension):
            logger.warning('sample does not end with "%s". naming will be wrong',self.extension)
        os.mkdir(self.output()['sampleresults'].path)

@inherits(Sample)
class countReadsSample(luigi.Task):
    def requires(self): return self.clone_parent()

    def output(self):
        return luigi.LocalTarget('{}/readcount.txt'.format(self.input()['sampleresults'].path))
    
    def run(self):
        (local['cat'][self.input()['sample'].path] | local['grep']['-c','@'] > self.output().path)()

@inherits(Sample)
class fastqcSample(luigi.Task):
    def requires(self): return self.clone_parent()

    def output(self):
        return (
            luigi.LocalTarget('{}/completed_{}'.format(self.input()['sampleresults'].path,self.task_family)),
            luigi.LocalTarget('{}/fastqc.zip'.format(self.input()['sampleresults'].path)),
            luigi.LocalTarget('{}/overrepresented_sequences.txt'.format(self.input()['sampleresults'].path))
            )
    
    def run(self):
        import zipfile
        local['fastqc']['-o',self.input()['sampleresults'].path,'-t','4']()
        zf = zipfile.ZipFile(self.output()[1])
        fh = zf.open('fastqc/fastqc_data.txt')
        for line in fh:
            if b'>>Overrepresented' in line: break
        with self.output()[2].open('wb') as f:
            f.write(line)
            for line in fh:
                if line == b'>>END_MODULE\n': break
                else: f.write(line)
        pathlib.Path(self.output()[0].path).touch()

#BDC tools possibly to be integrated
#@inherits(Sample)
#class cutadaptSample
#cutadapt -e 0.1 -a GATCGGAAGAGCACACGTCTGAACTCCAGTCACCGATGTATCTCGTATGC
# CLBGA_TBX2_all.fastq | gzip > CLBGA_TBX2_all_clean.fastq.gz

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
