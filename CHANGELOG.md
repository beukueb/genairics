# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

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