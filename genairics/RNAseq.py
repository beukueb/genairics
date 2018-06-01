#!/usr/bin/env python
#PBS -N RNAseqPipeline
#PBS -l nodes=1:ppn=16
#PBS -l walltime=72:00:00
#PBS -m be
"""
Full pipeline starting from BaseSpace fastq project
"""
from datetime import datetime, timedelta
import luigi, os, tempfile, pathlib, glob
from luigi.contrib.external_program import ExternalProgramTask
from luigi.util import inherits, requires
from plumbum import local, colors
import pandas as pd
import logging

# matplotlib => setup for exporting svg figures only
import matplotlib
matplotlib.use('SVG')
import matplotlib.pyplot as plt

## Tasks
from genairics import logger, config, gscripts, setupProject, setupSequencedSample
from genairics.datasources import BaseSpaceSource, mergeFASTQs
from genairics.resources import resourcedir, STARandRSEMindex

@inherits(mergeFASTQs)
class qualityCheck(luigi.Task):
    """
    Runs fastqc on all samples and makes an overall summary
    """
    def requires(self):
        return self.clone_parent()
        
    def output(self):
        return (
            luigi.LocalTarget('{}/{}/plumbing/completed_{}'.format(self.resultsdir,self.project,self.task_family)),
            luigi.LocalTarget('{}/{}/QCresults'.format(self.resultsdir,self.project)),
            luigi.LocalTarget('{}/{}/summaries/qcsummary.csv'.format(self.resultsdir,self.project))
        )

    def run(self):
        import zipfile
        from io import TextIOWrapper
        
        local[gscripts % 'qualitycheck.sh'](self.project, self.datadir)
        qclines = []
        for fqcfile in glob.glob(self.output()[1].path+'/*.zip'):
            zf = zipfile.ZipFile(fqcfile)
            with zf.open(fqcfile[fqcfile.rindex('/')+1:-4]+'/summary.txt') as f:
                ft = TextIOWrapper(f)
                summ = pd.read_csv(TextIOWrapper(f),sep='\t',header=None)
                qclines.append(summ[2].ix[0]+'\t'+'\t'.join(list(summ[0]))+'\n')
        with self.output()[2].open('w') as outfile:
            outfile.writelines(['\t'+'\t'.join(list(summ[1]))+'\n']+qclines)
        pathlib.Path(self.output()[0].path).touch()

# per sample subtasks
## STAR aligning
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

@inherits(STARconfig)
@inherits(setupSequencedSample)
class STARsample(luigi.Task):
    """
    Task that does the STAR alignment

    Currently fq's not moved first to tmp dir TODO
    Previous implementation that did that in the bash script:
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

    at the end tmp results were moved to final destination:
    if [ "$PBS_JOBID" ]; then
    mv $TMPDIR/alignmentResults $datadir/../results/${project}/alignmentResults${suffix}
    fi
    """
    def requires(self):
        return self.clone(setupSequencedSample)

    def output(self):
        return luigi.LocalTarget('{}/.completed_{}'.format(self.outfileDir,self.task_family))
        
    def run(self):
        stdout = local['STAR'](
            '--runThreadN', config.threads,
            '--genomeDir', resourcedir+'/ensembl/{species}/release-{release}/transcriptome_index'.format(
                species=self.genome,release=self.release),
            '--readFilesIn', self.infile1, *((self.infile2,) if self.infile2 else ()), 
	    '--readFilesCommand', self.readFilesCommand,
	    '--outFileNamePrefix', os.path.join(self.input().path,'./'),
	    '--outSAMtype', *self.outSAMtype.split(' '),
	    '--quantMode', *self.quantMode.split(' ')
        )
        if stdout: logger.info('%s output:\n%s',self.task_family,stdout)

        # Check point
        pathlib.Path(self.output().path).touch()

## RSEM counting
@inherits(STARconfig)
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

    def output(self):
        return luigi.LocalTarget('{}/.completed_{}'.format(self.outfileDir,self.task_family))

    def run(self):
        stdout = local['rsem-calculate-expression'](
            '-p', config.threads, '--alignments',
            *(('--paired-end',) if self.infile2 else ()),
            '--forward-prob', self.forwardprob,
            os.path.join(self.input()[0].path,'Aligned.toTranscriptome.out.bam'),
            resourcedir+'/ensembl/{species}/release-{release}/transcriptome_index/{species}'.format(
                species=self.genome,release=self.release),
            os.path.join(self.input()[0].path,os.path.basename(self.outfileDir))
        )
        if stdout: logger.info('%s output:\n%s',self.task_family,stdout)
        
        # Check point
        pathlib.Path(self.output().path).touch()

# the sample pipeline can inherit and clone the sample subtasks directly
@inherits(RSEMsample)
class processTranscriptomicSampleTask(luigi.Task):
    """
    This wrappers makes sure all the individuel sample tasks get run.
    Each task should be idempotent to avoid issues.
    """
    def output(self):
        return luigi.LocalTarget('{}/.completed_{}'.format(self.outfileDir,self.task_family))
    
    def run(self):
        self.clone(setupSequencedSample).run()
        self.clone(STARsample).run()
        self.clone(RSEMsample).run()
        pathlib.Path(self.output().path).touch()

# the all samples pipeline needs to inherit the sample pipeline configs
@inherits(mergeFASTQs)
@inherits(RSEMconfig)    
class processTranscriptomicSamples(luigi.Task):
    """
    Process transciptomic samples for RNAseq with STAR aligner
    """
    suffix = luigi.Parameter(default='',description='use when preparing for xenome filtering')

    def requires(self):
        return {
            'fastqs':self.clone(mergeFASTQs)
        }

    def output(self):
        return (
            luigi.LocalTarget('{}/{}/plumbing/completed_{}'.format(self.resultsdir,self.project,self.task_family)),
            luigi.LocalTarget('{}/{}/sampleResults'.format(self.resultsdir,self.project)),
        )

    def run(self):
        # Make output directory
        if not self.output()[1].exists(): os.mkdir(self.output()[1].path)

        # Run the sample subtasks
        for fastqfile in glob.glob(os.path.join(
                self.datadir,self.project,
                '*_R1.fastq.gz' if self.pairedEnd else '*.fastq.gz')
        ):
            sample = os.path.basename(fastqfile).replace('.fastq.gz','')
            processTranscriptomicSampleTask( #OPTIONAL future implement with yield
                infile1 = fastqfile,
                infile2 = fastqfile.replace('_R1.','_R2.') if self.pairedEnd else '',
                outfileDir = os.path.join(self.output()[1].path,sample), #optionally in future first to temp location
                **{k:self.param_kwargs[k] for k in RSEMconfig.get_param_names()}
            ).run()
        
        # Check point
        pathlib.Path(self.output()[0].path).touch()
        
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
        yield self.clone(mergeFASTQs)
        yield self.clone(qualityCheck)
        yield self.clone(processTranscriptomicSamples)
        yield self.clone(mergeAlignResults)
        yield self.clone(PCAplotCounts)
        if self.design: yield self.clone(diffexpTask)
