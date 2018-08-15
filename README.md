[![Latest Version](https://img.shields.io/pypi/v/genairics.svg)](https://pypi.python.org/pypi/genairics/)
[![Docker](https://img.shields.io/docker/automated/beukueb/genairics.svg)](https://hub.docker.com/r/beukueb/genairics/)
[![License](https://img.shields.io/pypi/l/genairics.svg)](https://pypi.python.org/pypi/genairics/)

# GENeric AIRtight omICS pipelines
<img title="genairics logo" src="gax_logo.svg" width="500">

## Design goals

### generic pipelines

The pipelines here available are mainly developed for my specific
bioinformatics needs and that of my collaborators. They are build up
in a generic way, and some of the functionality in the main genairics
package file might help or inspire you to build your own
pipelines. The core of the pipelines is build with
[luigi](https://luigi.readthedocs.io) and extensions are provided in
this package's initialization file.

### airtight pipelines

The pipelines are build so they can be started with a single,
fool-proof command.  This should allow collaborators, or scientists
wanting to replicate my results, to easily do so. A docker container
is provided with the package so the processing can be started up on
any platform.

### omics pipelines

The pipelines grow organically, as my research needs expand. I aim to
process any kind of data. If you want to use my set of pipelines, but
desire an expansion to make it more omics-like, contact me and we can
see if there are opportunities to collaborate. More generally,
everyone is welcome to leave suggestions in the [issues
section](https://github.com/beukueb/genairics/issues) of the
repository.

## Installation

### genairics package

#### Dependencies

Python 3 has to be installed: see https://www.python.org/downloads/ for instructions.

#### Prepare virtualenvwrapper [optional]

     sudo pip3 install virtualenvwrapper
     echo "export WORKON_HOME=~/Envs" >> ~/.bashrc
     echo "export VIRTUALENVWRAPPER_PYTHON=$(which python3)" >> ~/.bashrc
     . ~/.bashrc
     mkdir -p $WORKON_HOME
     . /usr/local/bin/virtualenvwrapper.sh
     mkvirtualenv -a ~/genairics -i ipython

#### Install

     workon genairics #only when working in virtualenv
     # For stable version:
     pip3 install genairics
     # For latest development version:
     # pip3 install git+https://github.com/dicaso/genairics.git

Start up console with `genairics console` and execute the following line:

    InstallDependencies()

### Get your BASESPACE_API_TOKEN accessToken

Follow the steps 1-5 from this link:
https://help.basespace.illumina.com/articles/tutorials/using-the-python-run-downloader/

	emacs ~/.BASESPACE_API #Store your accessToke here, instead of emacs use any editor you like
	chmod 600 ~/.BASESPACE_API #For security, only rw access for your user

### Prepare your HPC account [for UGent collaborators]

Go to https://www.ugent.be/hpc/en/access/faq/access to apply for access to the HPC.

#### add to your HPC ~/.bashrc =>

    export GAX_RESOURCES=$VSC_DATA_VO/resources
    export GAX_DATADIR=$VSC_DATA_VO_USER/data
    export GAX_RESULTSDIR=$VSC_DATA_VO_USER/results
    export BASESPACE_API_TOKEN= #Set this to your basespace api token
    export PATH=$VSC_DATA_VO/resources/bin:$PATH:~/.local/bin
    if [[ -v SET_LUIGI_FRIENDLY ]]; then module load pandas; unset SET_LUIGI_FRIENDLY; fi
    if [[ -v R_MODULE ]]; then module purge; module load R-bundle-Bioconductor; unset R_MODULE; fi

#### Execute the following commands

    module load pandas
    pip3 install --user --upgrade genairics
    mkdir $VSC_DATA_VO_USER/{data,results}

Rerun the first two of these lines whenever you need to upgrade your genairics version.

## Example run

### Docker

    docker run -v ~/resources:/resources -v ~/data:/data -v ~/results:/results \
	       --env-file ~/.BASESPACE_API beukueb/genairics RNAseq \
	       NSQ_Run240 --genome saccharomyces_cerevisiae

### qsub job

    genairics --job-launcher qsub RNAseq NSQ_Run240

## Epilogue

There comes a point in time when any human just has to develop their
own, fully-fledged computational genomics platform. This is not that
time for me, but it is good to set it as an aim: aiming for the stars,
landing somewhere on the moon. Of course, with help I should be able
cover more distance, so if you like this project and want to help out,
contact me.
