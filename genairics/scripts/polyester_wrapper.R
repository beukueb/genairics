#!/usr/bin/env Rscript

library(polyester)
library(Biostrings)

# Read commandline arguments => trailingOnly => only relevant args
args = commandArgs(trailingOnly = T)
print(args)
transcriptfile = args[1]
coverage = as.integer(args[2])
replicates = as.integer(args[3])
outdir = args[4]

# Processing
fasta = readDNAStringSet(transcriptfile)
readspertx = round(coverage * width(fasta) / 100)
fold_changes = matrix(rep(1,length(fasta)*2), nrow = length(fasta))
simulate_experiment(
	transcriptfile,
	reads_per_transcript = readspertx,
	num_reps = c(replicates,replicates),
	fold_changes = fold_changes,
	outdir=outdir
)
