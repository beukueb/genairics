#!/usr/bin/env Rscript

library("limma")

# Read commandline arguments => trailingOnly => only relevant args
args = commandArgs(trailingOnly = T)
print(args)
project = args[1]
datadir = args[2]
metafile = args[3]
design = args[4]
result_coef = 2

counts = read.table(paste(datadir,'../results',project,'summaries/RSEMcounts.csv',sep='/'),
       header = T, row.names=1, sep=',')
metadata = read.table(metafile, header = T, row.names=1, sep=',')
design = model.matrix(formula(design),data=metadata)
print(colnames(design))
#TODO colnames(design) = replace(':','.') for c in colnames(design)

# Fit DE model
svg(paste(datadir,'../results',project,'plumbing/voomedData.svg',sep='/'))
# png does not work on server -> x11 issue
voomedCounts = voom(counts,design=design,plot=T,normalize="quantile")
dev.off()

fit = lmFit(voomedCounts,design)
#fit_r = limma.lmFit(voomedCounts_r.rx2('E'),design_r,weights=voomedCounts_r.rx2('weights'))
#fit_r = limma.contrasts_fit(fit_r,contrasts_r)
fit = eBayes(fit)
print(summary(fit))
print(head(fit$coefficients))

# Export results
rankedResults = topTable(fit,coef=result_coef,n=dim(counts)[1])
write.table(rankedResults,
	file=paste(datadir,'../results',project,'summaries/DEexpression.csv',sep='/'),
	sep=',')