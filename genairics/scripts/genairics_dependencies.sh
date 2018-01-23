#!/bin/bash
set -x #Get all debugging info

# Set GAX_ENVS to GAX_REPOS if not set
export GAX_ENVS=${GAX_ENVS:-$GAX_REPOS}

# Set C[++] compilation env variables
export LIBRARY_PATH=$GAX_PREFIX/lib:$LIBRARY_PATH
export LD_LIBRARY_PATH=$GAX_PREFIX/lib:$LD_LIBRARY_PATH
export C_INCLUDE_PATH=$GAX_PREFIX/include
export CPLUS_INCLUDE_PATH=$GAX_PREFIX/include
#reference see https://gcc.gnu.org/onlinedocs/gcc/Environment-Variables.html

# Installs all dependencies for genairics to run its pipelines
mkdir -p $GAX_REPOS
mkdir -p $GAX_ENVS

# apt-get dependencies in Dockerfile, brew dependencies in README.md

# Enable genairics CLI argument completion
# https://github.com/kislyuk/argcomplete/
activate-global-python-argcomplete

## fastqc -> install with apt-get, brew, ...

## bowtie2
if [ ! $(command -v bowtie2) ]; then
    ### Info from http://bowtie-bio.sourceforge.net/bowtie2/faq.shtml
    # Does Bowtie 2 supersede Bowtie 1?
    # Mostly, but not entirely. If your reads are shorter than 50 bp, you might want to try both Bowtie 1 and Bowtie 2 and see # which gives better results in terms of speed and sensitivity. In our experiments, Bowtie 2 is generally superior to
    # Bowtie 1 for reads longer than 50 bp. For reads shorter than 50 bp, Bowtie 1 may or may not be preferable.
    cd $GAX_REPOS
    git clone https://github.com/BenLangmead/bowtie2.git && cd bowtie2
    # not using tbb lib => not a developer friendly library; no ./configure, prefix option, or make install
    make NO_TBB=1
    ln -s $GAX_REPOS/bowtie2/bowtie2 $GAX_PREFIX/bin/bowtie2
    ln -s $GAX_REPOS/bowtie2/bowtie2-build $GAX_PREFIX/bin/bowtie2-build
fi

## STAR
cd $GAX_REPOS
wget https://github.com/alexdobin/STAR/archive/2.5.3a.tar.gz
tar -xzf 2.5.3a.tar.gz
if [[ $OSTYPE == *"darwin"* ]]; then
    ln -s $GAX_REPOS/STAR-2.5.3a/bin/MacOSX_x86_64/STAR $GAX_PREFIX/bin/STAR
else
    ln -s $GAX_REPOS/STAR-2.5.3a/bin/Linux_x86_64_static/STAR $GAX_PREFIX/bin/STAR
fi

## RSEM
cd $GAX_REPOS
git clone https://github.com/deweylab/RSEM.git
cd RSEM
make
ln -s $GAX_REPOS/RSEM/rsem-prepare-reference $GAX_PREFIX/bin/rsem-prepare-reference
ln -s $GAX_REPOS/RSEM/rsem-calculate-expression $GAX_PREFIX/bin/rsem-calculate-expression

## bedtools
cd $GAX_REPOS
wget https://github.com/arq5x/bedtools2/releases/download/v2.25.0/bedtools-2.25.0.tar.gz
tar -zxvf bedtools-2.25.0.tar.gz
cd bedtools2
make
for program in $(ls bin); do
    ln -s $GAX_REPOS/bedtools2/bin/$program $GAX_PREFIX/bin/$program
done

## MACS2
virtualenv --python=python2.7 $GAX_ENVS/macs2_env
PYTHONPATH= $GAX_ENVS/macs2_env/bin/pip install numpy MACS2 --prefix=$GAX_ENVS/macs2_env
ln -s $GAX_ENVS/macs2_env/bin/macs2 $GAX_PREFIX/bin/macs2

## deeptools
### dependencies
#### cURL -> so cURL module does not have to be loaded
if [[ -v VSC_HOME ]]; then
    cd $GAX_REPOS
    git clone https://github.com/curl/curl.git && cd curl
    ./buildconf
    ./configure --prefix=$GAX_PREFIX
    make
    make install
fi
### main package
virtualenv --python=python3 $GAX_ENVS/deeptools_env
PYTHONPATH= $GAX_ENVS/deeptools_env/bin/pip install deeptools --prefix=$GAX_ENVS/deeptools_env
ln -s $GAX_ENVS/deeptools_env/bin/bamCoverage $GAX_PREFIX/bin/bamCoverage

## homer
cd $GAX_REPOS
mkdir homer && cd homer
wget http://homer.ucsd.edu/homer/configureHomer.pl
perl configureHomer.pl -install homer
ln -s $GAX_REPOS/homer/bin/makeTagDirectory $GAX_PREFIX/bin/makeTagDirectory
ln -s $GAX_REPOS/homer/bin/findPeaks $GAX_PREFIX/bin/findPeaks
ln -s $GAX_REPOS/homer/bin/pos2bed.pl $GAX_PREFIX/bin/pos2bed.pl
