#!/usr/bin/env python
"""
ChIP sequencing pipeline starting from BaseSpace fastq project

References:
 - http://jvanheld.github.io/cisreg_course/chip-seq/practical/chip-seq.html
 - http://crazyhottommy.blogspot.be/2015/06/chip-seq-analysis-part1.html
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
from genairics.resources import resourcedir, RetrieveGenome, Bowtie2Index, RetrieveBlacklist
from genairics.RNAseq import qualityCheck

### ChIP specific Task
class cutadaptConfig(luigi.Config):
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
    pairedEnd = luigi.BoolParameter(
        default=False,
        description='paired end sequencing reads (NOT IMPLEMENTED YET)'
    )

@inherits(cutadaptConfig)
class TrimFilterSample(luigi.Task):
    infile = luigi.Parameter()
    outfileDir = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(os.path.join(self.outfileDir,'trimmed.fq.gz'))
        
    def run(self):
        stdout = local['cutadapt'](
            '--cores', config.threads,
            '-a', self.adapter,
            '-e', self.errorRate,
            '-o', self.output().path,
            self.infile
        )
        if stdout: logger.info(stdout)

#subsampleTask => subsampling naar 30 miljoen indien meer

@inherits(TrimFilterSample)
@inherits(Bowtie2Index)
class Bowtie2MapSample(luigi.Task):
    def requires(self):
        return {
            'sample': self.clone(TrimFilterSample),
            'index': self.clone(Bowtie2Index)
            }
        
    def output(self):
        return luigi.LocalTarget(os.path.join(self.outfileDir,'alignment.bam'))

    def run(self):
        # run bowtie2 and store as bam file with mapping quality already filtered to mapQ 4
        stdout = (local['bowtie2'][
            '-p', config.threads,
            '-x', os.path.join(self.input()['index'][0].path,self.genome),
            '-U', self.input()['sample'].path #-U -> unpaired, TODO to start using paired will be with -1 and -2
        ] | local['samtools']['view', '-q', 4, '-Sbh', '-'] > self.output().path)()
        if stdout: logger.info(stdout)

@requires(Bowtie2MapSample)
class SamProcessSample(luigi.Task):
    def output(self):
        return [
            luigi.LocalTarget(os.path.join(self.outfileDir,'alignment_sorted.bam')),
            luigi.LocalTarget(os.path.join(self.outfileDir,'alignment_sorted.bai')),
            luigi.LocalTarget(os.path.join(self.outfileDir,'flagstatsummary.txt')),
            luigi.LocalTarget(os.path.join(self.outfileDir,'idxstats.txt'))
        ]

    def run(self):
        # sort output
        stdout = local['samtools']('sort', self.input().path, '-o', self.output()[0].path)

        # index output
        stdout += local['samtools']('index', self.output()[0].path)

        # replace unsorted bam with empty stub
        with self.input().open('wb') as f:
            f.truncate()
    
        # TODO samstat on bamfile
        #http://samstat.sourceforge.net/

        # stats: flagstat and per chromosome read stats
        stdout += (local['samtools']['flagstat', self.output()[0].path] > self.output()[2].path)()
        stdout += (local['samtools']['idxstats', self.output()[0].path] > self.output()[3].path)()

        # log
        if stdout: logger.info(stdout)

@requires(SamProcessSample)
class MakeSampleGenomeBrowserTrack(luigi.Task):
    """
    genome browser track file
    """
    def output(self):
        return luigi.LocalTarget(os.path.join(self.outfileDir,'alignment_coverage.bw'))

    def run(self):
        stdout = local['bamCoverage']('-b', self.input()[0].path, '–outFileFormat', 'bigwig', '-o', self.output().path)

# the sample pipeline can inherit and clone the subtasks directly
@inherits(MakeSampleGenomeBrowserTrack)
class processGenomicSampleTask(luigi.WrapperTask):
    def run(self):
        self.clone(TrimFilterSample).run()
        self.clone(Bowtie2MapSample).run()
        self.clone(SamProcessSample).run()
        self.clone(MakeSampleGenomeBrowserTrack).run()

# the all samples pipeline needs to inherit the sample pipeline configs
@inherits(mergeFASTQs)
@inherits(cutadaptConfig)    
@inherits(Bowtie2Index)
class processGenomicSamples(luigi.Task):
    """
    Process genomic samples (can be used for ChIP, ATAC, variant calling)
    """
    def requires(self):
        return {
            'fastqs': self.clone(mergeFASTQs)
        }

    def output(self):
        return (
            luigi.LocalTarget('{}/{}/plumbing/completed_{}'.format(self.resultsdir,self.project,self.task_family)),
            luigi.LocalTarget('{}/{}/alignmentResults'.format(self.resultsdir,self.project)),
        )

    def run(self):
        # Make output directory
        if not self.output()[1].exists(): os.mkdir(self.output()[1].path)

        # Run the sample subtasks
        for fastqfile in glob.glob(os.path.join(self.datadir,self.project,'*.fastq.gz')):
            sample = os.path.basename(fastqfile).replace('.fastq.gz','')
            processGenomicSampleTask( #OPTIONAL future implement with yield
                infile = fastqfile,
                outfileDir = os.path.join(self.output()[1].path,sample+'/'), #optionally in future first to temp location
                **{k:self.param_kwargs[k] for k in cutadaptConfig.get_param_names()}
            ).run()
        
        # Check point
        pathlib.Path(self.output()[0].path).touch()

@requires(processGenomicSamples)
class PeakCallingChIPsamples(luigi.Task):
    """
    performs the peak calling with macs2
    tries to match every ChIPseq sample with an input sample,
    if not working as expected you will have to change the filenames

    an input filename needs to contain 'input' or whatever you set as inputFileMarker
    a matching sample file, needs to contain everything of the input filename, before
    the 'input'/inputFileMarker section

    e.g. inputfile => IMR32_input.fq.gz
    e.g. matching file => IMR32_H3K27ac.fq.gz, as it also contains 'IMR32_'
    """
    inputFileMarker = luigi.Parameter(
        default='input',
        description='should be in filename of every input sample'
    )
    
    def run(self):
        inputfiles = {i for i in glob.glob(os.path.join(self.input()[0].path,'*{}*'.format(self.inputFileMarker)))}
        inputmatchmap = {os.path.basename(i).split(self.inputFileMarker)[0]:i for i in inputfiles}
        if len(inputfiles) != len(inputmatchmap):
            logger.error('some inputfiles have non unique prefix before input marker "%s" (%s)',
                         self.inputFileMarker,inputfiles)
            raise Exception()
        for sample in glob.glob(os.path.join(self.input()[0].path,'*')):
            if sample not in inputfiles:
                foundMarker = False
                for marker in inputmatchmap:
                    if os.basename(sample).startswith(marker):
                        foundMarker = marker
                        break
                if not foundMarker:
                    logger.warning('no matching input file found for %s',os.path.basename(sample))
                else:
                    #macs2
                    stdout = local['macs2'](
                        'callpeak', '-t', os.path.join(sample,'alignment_sorted.bam'),
                        '-c', os.path.join(inputmatchmap[foundMarker],'alignment_sorted.bam'),
                        '--outdir', sample, '-n', 'diff_peaks', '-q', 0.05, '-g', 'hs', '--bdg'
                    )
                    if stdout: logger.info(stdout)

                    # homer
                    stdout = local['makeTagDirectory'](
                        os.path.join(sample,'homer_tags'),
                        os.path.join(sample,'alignment_sorted.bam')
                    )
                    stdout = local['makeTagDirectory'](
                        #TODO good place in the input align dir so does not compute twice in case of reuse
                        os.path.join(sample,'homer_tags_input'),
                        os.path.join(inputmatchmap[foundMarker],'alignment_sorted.bam')
                    )
                    stdout += local['findPeaks'](
                        os.path.join(sample,'homer_tags'),
                        '-style', 'factor',
                        '-o', os.path.join(sample,'homer_peaks_found'),
                        '-i', os.path.join(sample,'homer_tags_input')
                    )
                    stdout += (local['pos2bed.pl'][os.path.join(sample,'homer_peaks_found')]
                               > os.path.join(sample,'homer_peaks.bed'))()
                    if stdout: logger.info(stdout)


#class ClusterBamFiles(luigi.Task):
    #DeepTools for clustering of bam files
    #multiBamSummary bins --bamfiles sam_1/CLBGA_INPUT_F_sorted.bam sam_2/CLBGA_TBX2_F_sorted.bam sam_6/SKNAS_INPUT_B_sorted.bam sam_7/SKNAS_TBX2_B_sorted.bam sam_8/SKNAS_H3K27ac_B_sorted.bam -out multiBamSummary_bam_Run296.npz --labels CLBGA_INPUT CLBGA_TBX2 SKNAS_INPUT SKNAS_TBX2 SKNAS_H3K27ac
    #plotCorrelation --corData multiBamSummary_bam_Run296.npz --plotFile correlation_peaks.pdf --outFileCorMatrix correlation_peaks_matrix.txt --whatToPlot heatmap --corMethod pearson --plotNumbers --removeOutliers

@inherits(BaseSpaceSource)
@inherits(PeakCallingChIPsamples)
class ChIPseq(luigi.WrapperTask):
    def requires(self):
        yield self.clone(setupProject)
        yield self.clone(BaseSpaceSource)
        yield self.clone(mergeFASTQs)
        yield self.clone(qualityCheck)
        yield self.clone(processGenomicSamples)
        yield self.clone(PeakCallingChIPsamples)
