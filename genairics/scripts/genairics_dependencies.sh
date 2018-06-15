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

## wrapprogram function -> takes program ($1), and wraps module ($2) needed on hpc
## if $3 == nopurge other modules are not purged, default is to purge
function wrapprogram {
    wrapperscript=$GAX_PREFIX/bin/$(basename $1)
    echo '#!/bin/env bash' > $wrapperscript
    if [[ ! "$3" == "nopurge" ]]; then
	echo 'module purge' >> $wrapperscript
    fi
    echo "module load $2" >> $wrapperscript
    echo $1 '"$@"' >> $wrapperscript
    chmod +x $wrapperscript
}

## fastqc -> install with apt-get, brew, ...
if [[ -v VSC_HOME ]]; then
    wrapprogram fastqc FastQC
fi

## Trim Galore
cd $GAX_REPOS
curl -fsSL https://github.com/FelixKrueger/TrimGalore/archive/0.4.5.tar.gz -o trim_galore.tar.gz
tar xvzf trim_galore.tar.gz
rm trim_galore.tar.gz
if [[ -v VSC_HOME ]]; then
    wrapprogram $GAX_REPOS/TrimGalore-0.4.5/trim_galore fastqc nopurge
else
    ln -s $GAX_REPOS/TrimGalore-0.4.5/trim_galore $GAX_PREFIX/bin/trim_galore
fi

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

## Quality control tools
### BamQC
cd $GAX_REPOS
git clone https://github.com/s-andrews/BamQC.git && cd BamQC
if [[ -v VSC_HOME ]]; then
    module load ant
elif [[ $OSTYPE == *"darwin"* ]]; then
    brew install ant
fi
ant
chmod 755 bin/bamqc
ln -s $GAX_REPOS/BamQC/bin/bamqc $GAX_PREFIX/bin/bamqc

### samstat
cd $GAX_REPOS
wget https://downloads.sourceforge.net/project/samstat/samstat-1.5.1.tar.gz
tar -zxf samstat-1.5.1.tar.gz && rm samstat-1.5.1.tar.gz && cd samstat-1.5.1
./configure
make
ln -s $GAX_REPOS/samstat-1.5.1/src/samstat $GAX_PREFIX/bin/samstat

### RSeQC #=> TODO not fully operational yet, is not possible to symbolically link executable
#### download gene models (further info: https://sourceforge.net/projects/rseqc/files/BED/Human_Homo_sapiens/)
cd $GAX_REPOS && mkdir RSeQC_gene_models && cd RSeQC_gene_models
for rseqcref in hg38_rRNA.bed.gz hg38.HouseKeepingGenes.bed.gz; do
    wget https://sourceforge.net/projects/rseqc/files/BED/Human_Homo_sapiens/$rseqcref
    gunzip $rseqcref
done
if [[ -v VSC_HOME ]]; then
    module load LZO
    virtualenv --python=python2.7 $GAX_ENVS/rseqc_env
    PYTHONPATH= $GAX_ENVS/rseqc_env/bin/pip install RSeQC --prefix=$GAX_ENVS/rseqc_env
    #PYTHONPATH= $GAX_ENVS/rseqc_env/bin/python $GAX_ENVS/rseqc_env/bin/geneBody_coverage.py -h
elif [[ $OSTYPE == *"darwin"* ]]; then
    brew install lzo
    pip2 install --user RSeQC
fi

## RSEM
cd $GAX_REPOS
git clone https://github.com/deweylab/RSEM.git && cd RSEM && make
if [[ -v VSC_HOME ]]; then
    wrapprogram $GAX_REPOS/RSEM/rsem-prepare-reference Perl
    wrapprogram $GAX_REPOS/RSEM/rsem-calculate-expression Perl
else
    ln -s $GAX_REPOS/RSEM/rsem-prepare-reference $GAX_PREFIX/bin/rsem-prepare-reference
    ln -s $GAX_REPOS/RSEM/rsem-calculate-expression $GAX_PREFIX/bin/rsem-calculate-expression
fi

## bedtools
cd $GAX_REPOS
wget https://github.com/arq5x/bedtools2/releases/download/v2.25.0/bedtools-2.25.0.tar.gz
tar -zxvf bedtools-2.25.0.tar.gz
cd bedtools2 && make
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

## freebayes
cd $GAX_REPOS
git clone --recursive https://github.com/ekg/freebayes.git && cd freebayes
make
ln -s $GAX_REPOS/freebayes/bin/freebayes $GAX_PREFIX/bin/freebayes
ln -s $GAX_REPOS/freebayes/bin/bamleftalign $GAX_PREFIX/bin/bamleftalign
