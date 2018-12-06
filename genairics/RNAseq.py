#-*- coding: utf-8 -*-
"""RNA sequencing pipeline starting from BaseSpace fastq project

For help on settings run `genairics RNAseq -h`
"""
from datetime import datetime, timedelta
import luigi, os, tempfile, pathlib, glob
from luigi.contrib.external_program import ExternalProgramTask
from luigi.util import inherits, requires
from genairics.targets import LuigiLocalTargetAttribute
from plumbum import local, colors
import pandas as pd, matplotlib.pyplot as plt
import logging

## Tasks
from genairics import logger, config, gscripts, setupProject, setupSequencedSample, processSamplesIndividually
from genairics.datasources import BaseSpaceSource, mergeSampleFASTQs
from genairics.resources import resourcedir, STARandRSEMindex

# per sample subtasks
@requires(mergeSampleFASTQs)
class sampleQualityCheck(luigi.Task):
    """Check the quality of a single sample

    Uses fastqc.
    """
    def output(self):
        return luigi.LocalTarget(os.path.join(self.outfileDir,'QCresults'))

    def run(self):
        tmpdir = self.output().path+'_tmp'
        os.mkdir(tmpdir)
        stdout = local['fastqc'](
            '-o', tmpdir,
            '-t', config.threads,
            self.input()[0].path,
            *((self.input()[1].path,) if self.pairedEnd else ())
        )
        os.rename(tmpdir,self.output().path)

## read quality trimming
class cutadaptConfig(luigi.Config):
    """
    Info: http://cutadapt.readthedocs.io/en/stable/guide.html
    """
    trimReads = luigi.BoolParameter(
        default = False,
        description = "trim the reads using cutadapt"
    )
    trimAdapter = luigi.BoolParameter(
        default = False,
        description = "trim the adapter specified by --adapter"
    )
    adapter = luigi.Parameter(
        default = "GATCGGAAGAGCACACGTCTGAACTCCAGTCACCGATGTATCTCGTATGC",
        description = "cutadapt adapter to trim"
    )
    errorRate = luigi.FloatParameter(
        default = 0.1,
        description = "allowed error rate => errors #/length mapping"
    )
    removeUntrimmedFile = luigi.BoolParameter(
        default = False,
        description = "remove the original untrimmed fastq"
    )
    cutadaptCLIargs = luigi.Parameter(
        default = "-q 20 -m 30",
        description = """Include all the arguments for cutadapt here, 
        except for input and output related files.
        If running on the command line, do not forget to inclose with quotes.
        """
    )

@inherits(cutadaptConfig)
@inherits(mergeSampleFASTQs)
class cutadaptSampleTask(luigi.Task):
    """Apply cutadapt to sample

    Currently a CLI configuration string needs to be provided,
    allowing as flexible a use as possible. You may need to look
    into the cutadapt documentation to know which arguments to provide.

    TODO implement for paired end
    """
    def requires(self):
        return self.clone(mergeSampleFASTQs)
        
    def run(self):
        if self.trimReads:
            import shutil
            for inputfile in self.input():
                untrimmed = os.path.join(
                    self.outfileDir,
                    os.path.basename(inputfile.path).replace('.fastq.gz','_untrimmed.fastq.gz')
                )
                shutil.move(inputfile.path,untrimmed)
                stdout = local['cutadapt'](
                    '--cores', config.threads,
                    *(('-a', self.adapter) if self.trimAdapter else ()),
                    *(('-e', self.errorRate) if self.errorRate else ()),
                    *(self.cutadaptCLIargs.split()),
                    '-o', inputfile.path, #is actually output file here (overwriting original infile)
                    untrimmed
                )
                if stdout: logger.info(stdout)
                if self.removeUntrimmedFile: os.unlink(untrimmed)
                
        if self.output().pathExists(): self.output().touch()

    def output(self):
        # only first read or single read fastq marked complete
        return LuigiLocalTargetAttribute(
            self.input()[0].path, self.task_family, 'done'
        )
        
## STAR aligning
@inherits(cutadaptConfig)
@inherits(STARandRSEMindex)
class STARconfig(luigi.Config):
    """
    Reference: https://github.com/alexdobin/STAR
    """
    readFilesCommand = luigi.Parameter(
        default='zcat',
        description='STAR readFilesCommand parameter'
    )
    outSAMtype = luigi.Parameter(
        default='BAM SortedByCoordinate',
        description='STAR outSAMtype parameter (can contain more than one argument separated by 1 space)'
    )
    quantMode = luigi.Parameter(
        default='TranscriptomeSAM GeneCounts',
        description='STAR quantMode parameter (can contain more than one argument separated by 1 space)'
    )
    removeFASTQs = luigi.BoolParameter(
        default = True,
        description = 'The merged FASTQs are removed after mapping.'
    )
    samstat = luigi.BoolParameter(
        default = True,
        description = 'Run samstat on transcriptome bam file.'
    )

@inherits(STARconfig)
@inherits(mergeSampleFASTQs)
class STARsample(luigi.Task):
    """
    Task that does the STAR alignment
    """
    def requires(self):
        return self.clone(mergeSampleFASTQs)

    def run(self):
        stdout = local['STAR'](
            '--runThreadN', config.threads,
            '--genomeDir', resourcedir+'/ensembl/{species}/release-{release}/transcriptome_index'.format(
                species=self.species,release=self.release),
            '--readFilesIn', self.input()[0].path,
            *((self.input()[1].path,) if self.pairedEnd else ()),
            *(('--outFilterScoreMinOverLread', 0.3, '--outFilterMatchNminOverLread', 0.3) if self.pairedEnd else ()),
	    '--readFilesCommand', self.readFilesCommand,
	    '--outFileNamePrefix', os.path.join(self.outfileDir,'./'),
	    '--outSAMtype', *self.outSAMtype.split(' '),
	    '--quantMode', *self.quantMode.split(' ')
        )
        if stdout: logger.info('%s output:\n%s',self.task_family,stdout)

        # Remove processed FASTQs
        if self.removeFASTQs:
            os.unlink(self.input()[0].path)
            if self.pairedEnd: os.unlink(self.input()[1].path)

        # Samstat
        if self.samstat:
            stdout = local['samstat'](
                os.path.join(self.outfileDir,'Aligned.toTranscriptome.out.bam')
            )
        
        # Check point
        pathlib.Path(self.output().path).touch()

    def output(self):
        return luigi.LocalTarget('{}/.completed_{}'.format(self.outfileDir,self.task_family))

## BAM processing
### genome bw coverage
class coverageConfig(luigi.Config):
    """coverage settings

    Includes options for sorting and indexing the bam files for which
    the coverage bw will be made
    """
    skipBWcoverage = luigi.BoolParameter(False,description='Skip making bw coverage files.')
    normalizeTo1x = luigi.IntParameter(
        default=0,
        description="""
        bamCoverage normalization option. If not provided will default to `--normalizeUsing RPKM`.
        Else int needs to be provided of genome size to pass to --effectiveGenomeSize and --normalizeUsing RPGC,
        e.g. 2451960000 for human genome.
        """
    )

@inherits(STARsample)
@inherits(coverageConfig)
class coverageTask(luigi.Task):
    """coverage task

    Sorts, indexes bam file and makes bw coverage file.
    """
    def requires(self):
        return self.clone(STARsample)
    
    def run(self):
        if not self.skipBWcoverage:
            # Rename bam before processing
            bwfile = os.path.join(self.outfileDir,'Aligned.sortedByCoord.out.bw')
            bamfile = os.path.join(self.outfileDir,'Aligned.sortedByCoord.out.bam')
            #bamfileOriginal = os.path.join(self.outfileDir,'Aligned.sortedByCoord.unsorted.bam')
            #os.rename(bamfile,bamfileOriginal)
    
            # Sort => should already be sorted
            #stdout = local['samtools']('sort', '-o', bamfile, bamfileOriginal)
            #logger.info(stdout)
    
            # Index
            stdout = local['samtools']('index', bamfile)
            logger.info(stdout)
            
            # Coverage
            with local.env(PYTHONPATH=''):
                stdout = local['bamCoverage'](
                    '-p', str(config.threads),
                    *(
                        ('--normalizeUsing','RPGC','--effectiveGenomeSize',self.normalizeTo1x)
                        if self.normalizeTo1x else ('--normalizeUsing','RPKM',)
                    ),
                    #'--extendReads', #TODO make possible for both single/paired end
    		    '-b', bamfile, '-o', bwfile 
                )
                if stdout: logger.info(stdout)
    
        # Check point
        pathlib.Path(self.output().path).touch()

    def output(self):
        return luigi.LocalTarget('{}/.completed_{}'.format(self.outfileDir,self.task_family))

## RSEM counting
@inherits(STARconfig)
@inherits(coverageConfig)
class RSEMconfig(luigi.Config):
    """
    Reference: http://deweylab.biostat.wisc.edu/rsem/README.html
    http://deweylab.biostat.wisc.edu/rsem/rsem-calculate-expression.html

    Important documentation:
    --forward-prob <double> Probability of generating a read from the
    forward strand of a transcript. Set to 1 for a strand-specific
    protocol where all (upstream) reads are derived from the forward
    strand, 0 for a strand-specific protocol where all (upstream) read
    are derived from the reverse strand, or 0.5 for a non-strand-specific
    protocol.
    """
    forwardprob = luigi.FloatParameter(
        default=0.5,
        description='stranded seguencing [0 for illumina stranded], or non stranded [0.5]'
    )
    
@inherits(RSEMconfig)
@inherits(STARsample)
class RSEMsample(luigi.Task):
    def requires(self):
        return [
            self.clone(setupSequencedSample),
            self.clone(STARsample)
        ]

    def run(self):
        stdout = local['rsem-calculate-expression'](
            '-p', config.threads, '--alignments',
            *(('--paired-end',) if self.pairedEnd else ()),
            '--forward-prob', self.forwardprob,
            os.path.join(self.input()[0].path,'Aligned.toTranscriptome.out.bam'),
            resourcedir+'/ensembl/{species}/release-{release}/transcriptome_index/{species}'.format(
                species=self.species,release=self.release),
            os.path.join(self.input()[0].path,os.path.basename(self.outfileDir))
        )
        if stdout: logger.info('%s output:\n%s',self.task_family,stdout)
        
        # Check point
        pathlib.Path(self.output().path).touch()

    def output(self):
        return luigi.LocalTarget('{}/.completed_{}'.format(self.outfileDir,self.task_family))

# the sample pipeline can inherit and clone the sample subtasks directly
@inherits(RSEMsample)
class processTranscriptomicSampleTask(luigi.Task):
    """
    This wrappers makes sure all the individuel sample tasks get run.
    Each task should be idempotent to avoid issues.
    """
    
    def run(self):
        #yield subtasks; if completed will go to next subtask
        tasks = [
            setupSequencedSample,
            mergeSampleFASTQs,
            sampleQualityCheck,
            cutadaptSampleTask,
            STARsample,
            RSEMsample,
            coverageTask
        ]
        for t in tasks:
            t = self.clone(t)
            if not t.complete(): t.run()

        pathlib.Path(self.output().path).touch()

    def output(self):
        return luigi.LocalTarget('{}/.completed_{}'.format(self.outfileDir,self.task_family))

# the all samples pipeline needs to inherit the sample pipeline configs
@inherits(setupProject)
@inherits(RSEMconfig)    
class processTranscriptomicSamples(luigi.Task):
    """
    Process transciptomic samples for RNAseq with STAR aligner
    """
    pairedEnd = luigi.BoolParameter(
        default=False,
        description='paired end sequencing reads'
    )
    suffix = luigi.Parameter(default='',description='use when preparing for xenome filtering')

    def output(self):
        return (
            luigi.LocalTarget('{}/{}/plumbing/completed_{}'.format(self.resultsdir,self.project,self.task_family)),
            luigi.LocalTarget('{}/{}/sampleResults'.format(self.resultsdir,self.project)),
        )

    def run(self):
        # Make output directory
        if not self.output()[1].exists(): os.mkdir(self.output()[1].path)

        # Run the sample subtasks. Optionally in future yield list of the sample tasks to process in parallel
        for fastqdir in glob.glob(os.path.join(self.datadir, self.project, '*')):
            sample = os.path.basename(fastqdir)
            pTSTask = processTranscriptomicSampleTask(
                sampleDir = fastqdir,
                pairedEnd = self.pairedEnd,
                outfileDir = os.path.join(self.output()[1].path,sample),
                **{k:self.param_kwargs[k] for k in RSEMconfig.get_param_names()}
            )
            if not pTSTask.complete(): pTSTask.run()
        
        # Check point
        pathlib.Path(self.output()[0].path).touch()

# Merging sample to project tasks
## QC - requires only setupProject so that other pipelines can also use
@requires(processSamplesIndividually)
class mergeQualityChecks(luigi.Task):
    """
    Runs fastqc on all samples and makes an overall summary
    """
    def run(self):
        import zipfile
        from io import TextIOWrapper

        qczips = glob.glob(
            os.path.join(self.input()[1].path,'*/QCresults/*.zip')
        )
        if not qczips:
            raise Exception(
                """No quality control output.
                Check that the task that runs before finished correctly.
                To be able to use this merge task in different pipelines,
                it only inherits setupProject, it therefore does not require
                completeness of the previous task to run. This should be taken
                care of by the the wrapper task.
                """
            )
        
        qclines = []
        for fqcfile in qczips:
            zf = zipfile.ZipFile(fqcfile)
            with zf.open(fqcfile[fqcfile.rindex('/')+1:-4]+'/summary.txt') as f:
                ft = TextIOWrapper(f)
                summ = pd.read_csv(TextIOWrapper(f),sep='\t',header=None)
                qclines.append(summ[2].ix[0]+'\t'+'\t'.join(list(summ[0]))+'\n')
        with self.output().open('w') as outfile:
            outfile.writelines(['\t'+'\t'.join(list(summ[1]))+'\n']+qclines)

    def output(self):
        return luigi.LocalTarget(
            '{}/{}/summaries/qcsummary.csv'.format(
                self.requiredSampleTask.resultsdir,
                self.requiredSampleTask.project
            )
        )

@requires(processTranscriptomicSamples)
class mergeAlignResults(luigi.Task):
    """
    Merge the align and count results
    """

    def output(self):
        return (
            luigi.LocalTarget('{}/{}/plumbing/completed_{}'.format(self.resultsdir,self.project,self.task_family)),
            luigi.LocalTarget('{}/{}/summaries/STARcounts.csv'.format(self.resultsdir,self.project)),
            luigi.LocalTarget('{}/{}/summaries/RSEMcounts.csv'.format(self.resultsdir,self.project))
        )

    def run(self):
        #Process STAR counts
        amb = []
        counts = []
        amb_annot = counts_annot = None
        samples = []
        for dir in glob.glob(os.path.join(self.input()[1].path,'*')):
            f = open(os.path.join(dir,'ReadsPerGene.out.tab'))
            f = f.readlines()
            amb.append([int(l.split()[1]) for l in f[:4]])
            if not amb_annot: amb_annot = [l.split()[0] for l in f[:4]]
            f = f[4:]
            if not counts_annot: counts_annot = [l.split()[0] for l in f]
            else:
                assert counts_annot == [l.split()[0] for l in f]
            counts.append([int(l.split()[1]) for l in f])
            samples.append(dir[dir.rindex('/')+1:])
        # Alignment summary file
        counts_df = pd.DataFrame(counts,columns=counts_annot,index=samples).transpose()
        counts_df.to_csv(self.output()[1].path)
    
        # Process RSEM counts
        counts = {}
        samples = []
        for gfile in glob.glob(os.path.join(self.input()[1].path,'*/*.genes.results')):
            sdf = pd.read_table(gfile,index_col=0)
            counts[gfile[gfile.rindex('/')+1:-14]] = sdf.expected_count

        # Counts summary file
        counts_df = pd.DataFrame(counts)
        counts_df.to_csv(self.output()[2].path)
        
        # Check point
        pathlib.Path(self.output()[0].path).touch()

@requires(mergeAlignResults)
class PCAplotCounts(luigi.Task):
    sampleAnnotator = luigi.Parameter(
        default = '_',
        description = 'the string that separates annotation parts in the sample filename'
    )
    annotatorRelevant = luigi.IntParameter(
        default = 1,
        description = 'the number of relevant annotation parts in the sample filename'
    )
    countsFilter = luigi.FloatParameter(
        default = 1,
        description = 'the minimum average number (over all samples) of reads required for a gene for further analysis'
    )
    PCAcomponents = luigi.IntParameter(
        default = 3,
        description = 'number of PCA components to calculate'
    )
    
    def output(self):
        return [
            luigi.LocalTarget('{}/{}/summaries/PCAplot.svg'.format(self.resultsdir,self.project)),
            luigi.LocalTarget('{}/{}/summaries/PCAvars.svg'.format(self.resultsdir,self.project)),
            luigi.LocalTarget('{}/{}/summaries/PCAcomps.csv'.format(self.resultsdir,self.project)),
            luigi.LocalTarget('{}/{}/summaries/cumulativeReads.svg'.format(self.resultsdir,self.project)),
        ]

    def run(self):
        import matplotlib
        matplotlib.use('svg')
        import matplotlib.pyplot as plt
        import seaborn as sns
        import numpy as np
        from sklearn import preprocessing
        from sklearn.decomposition import PCA as sklearnPCA

        # Load counts
        counts = pd.read_csv(self.input()[2].path, index_col = 'gene_id')

        # Cumulative read count distribution
        figcums,axcums = plt.subplots()
        axcums.set_xscale("log", nonposx='clip', basex = 10)
        generange = range(1,len(counts)+1)
        for c in counts:
            totalc = counts[c].sum()
            axcums.plot(
                generange,
                counts[c].sort_values(ascending=False).cumsum()*100/totalc,
                label = c
            )
        axcums.set_xlabel('Number of genes')
        axcums.set_ylabel('Cumulative % of total reads')
        axcums.legend()
        figcums.savefig(self.output()[3].path)
        
        # Filter counts
        beforeFiltering = len(counts)
        counts = counts[counts.sum(axis=1) >= self.countsFilter * len(counts.columns)]
        logger.info('Remaining %s of %s after filtering',len(counts),beforeFiltering)
        # Normalize
        quantile_transformer = preprocessing.QuantileTransformer(
            output_distribution = 'normal',
            n_quantiles = 100,
            random_state = 0
        )
        X_norm = quantile_transformer.fit_transform(counts.T.as_matrix())
        #X_scaled = preprocessing.scale(counts.as_matrix())
        #X_norm = (X - X.min())/(X.max() - X.min())
        # Transform counts
        X_tran = np.log(X_norm + abs(X_norm.min()) + 1)
        pca = sklearnPCA(n_components=self.PCAcomponents)
        transformed = pd.DataFrame(
            pca.fit_transform(X_tran), index = counts.columns,
            columns = ['PC{}'.format(pc+1) for pc in range(self.PCAcomponents)]
        )
        transformed['annotation'] = transformed.T.apply(
            lambda x: ' '.join(x.name.split(self.sampleAnnotator)[:self.annotatorRelevant])
        )
        pcaComponents = pd.DataFrame(pca.components_.T,index=counts.index,columns=transformed.columns[:-1])
        pcaComponents.to_csv(self.output()[2].path)
        # Make figures
        ## PC plot
        fig = sns.lmplot('PC1', 'PC2', data = transformed, hue = 'annotation', fit_reg = False, scatter_kws={'s':50})
        fig.savefig(self.output()[0].path)
        ## PC variance plot
        fix, ax = plt.subplots()
        sns.barplot(np.arange(self.PCAcomponents)+1, pca.explained_variance_ratio_ * 100, ax=ax)
        ax.set_xlabel('PCA component')
        ax.set_ylabel('% variance explained')
        fix.savefig(self.output()[1].path)
        
@requires(mergeAlignResults)
class diffexpTask(luigi.Task):
    design = luigi.Parameter(default='',
                             description='model design for differential expression analysis')
    
    def output(self):
        return (
            luigi.LocalTarget('{}/{}/plumbing/completed_{}'.format(self.resultsdir,self.project,self.task_family)),
            luigi.LocalTarget('{}/{}/summaries/DEexpression.csv'.format(self.resultsdir,self.project))
        )

    def run(self):
        if not self.metafile:
            samples = glob.glob('{}/{}/sampleResults/*'.format(self.resultsdir,self.project))
            samples = pd.DataFrame(
                {'bam_location':samples,
                 'alignment_dir_size':[local['du']['-sh'](s).split('\t')[0] for s in samples]},
                index = [os.path.basename(s) for s in samples]
            )
            metafile = '{}/{}/metadata/samples.csv'.format(self.resultsdir,self.project)
            samples.to_csv(metafile)
            msg = colors.red | '''
                metafile needs to be provided to run DE analysis
                a template file has been generated for you ({})
                adjust file to match your design, add the above file path
                as input "metafile" for the pipeline and rerun
                '''.format(metafile)
            logger.error(msg)
            raise Exception()
        with local.env(R_MODULE="SET"):
            local['bash'][
                '-l','-c', ' '.join(
                    ['Rscript', gscripts % 'simpleDEvoom.R',
                     self.project, self.datadir, self.metafile, self.design]
                )]()
        pathlib.Path(self.output()[0].path).touch()

@inherits(BaseSpaceSource)
@inherits(PCAplotCounts)
@inherits(diffexpTask)
class RNAseq(luigi.WrapperTask):
    def requires(self):
        yield self.clone(setupProject)
        yield self.clone(BaseSpaceSource)
        sampleTask = self.clone(processTranscriptomicSamples)
        yield processSamplesIndividually(requiredSampleTask = sampleTask)
        yield mergeQualityChecks(requiredSampleTask = sampleTask)
        yield self.clone(mergeAlignResults)
        yield self.clone(PCAplotCounts)
        if self.design: yield self.clone(diffexpTask)
