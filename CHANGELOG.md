# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]
### Added
- ProgramTarget in genairics.targets, for program dependencies.
- --cluster-PPN option for qsub job-launcher to specify number of
processors per node to request.
- Created genairics.targets, genairics.tasks and genairics.config.
### Changed
- runWorkflow now only prints out task info if --verbose
- coverageTask to RNAseq pipeline to generate bw coverage
file. this also sorts the bam and creates its index for
visualization in a genome browser.
- Moved a lot of code out of genairics.__init__ into the more relevant
submodules targets, tasks and config

## [0.2.1] - 2018-06-19
### Added
- setupProject and ProjectTask offer getLogger method.
- Example hello world script for external pipelines.

### Fixed
- Starting through qsub no longer worked because of changed bool
flag arguments. Preparing qsub env variables and reading them fixed.

### Changed
- setupLogging deprecated

## [0.2.0] - 2018-06-18
### Added
- External pipelines in genairics CLI through env variable GAX_PIPEX.
- processSamplesIndividually task that acts as a checkpoint reference task
  for sample results merging task that can be agnostic of the
  sample specific processing task.
- pairedEnd processing operational.

### Fixed
- CLI bool arguments can now simply be provided as a flag,
  e.g. `--pairedEnd`, and not `--pairedEnd True` as was required before.

### Changed
- merging of FASTQs no longer at project level but at sample
  level. Unmerged FASTQs are no longer moved to _original_FASTQs
  subfolder. The merged FASTQ are put in the result sample
  subfolder. By default they are deleted after the singel sample
  processing steps, as by then usually only the bam files are required.
