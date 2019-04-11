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
if [[ ! -d $GAX_PREFIX/bin ]]; then mkdir $GAX_PREFIX/bin; fi

# Add GAX_PREFIX bin to path, to be sure dependencies that are already installed are found
export PATH=$GAX_PREFIX/bin:$PATH

# Platform package dependencies (Debian, RPM-based and MacOSX supported through apt-get, yum and brew)
# for other *nix ditributions it is necessary to install these dependencies up front
# or use the docker image. To install these packages set GAX_INSTALL_PLATFORM_PACKAGES
# in the shell where you will execute this script.
if [[ -v GAX_INSTALL_PLATFORM_PACKAGES ]]; then 
    if command -v apt-get; then
	sudo apt-get install -y git unzip rsync default-jre ant fastqc samtools bedtools r-base cmake
	sudo apt-get install gfortran libblas-dev # deps for R logspline, polyester dependency
    elif command -v yum; then
	sudo yum install -y git unzip rsync java-1.8.0-openjdk ant samtools BEDTools R cmake
	#fastqc package not available with yum
    elif command -v brew; then
	brew install git rsync java ant fastqc samtools bedtools cmake
	brew install openblas
	brew install r --with-openblas
	brew install gfortran
    fi
fi

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

# R packages
export R_LIBS=$GAX_PREFIX/Rlibs
if [[ ! -d $R_LIBS ]]; then
    mkdir $R_LIBS
    Rscript -e 'source("http://bioconductor.org/biocLite.R")' -e 'biocLite(c("limma"))' \
	    -e 'biocLite(c("polyester"))'
fi

## fastqc
if [[ -v VSC_HOME ]]; then
    wrapprogram fastqc FastQC
elif ! command -v fastqc; then
    # Intstalls fastqc for distro's not offering it as a package
    cd $GAX_REPOS
    git clone https://github.com/s-andrews/FastQC && cd FastQC
    sed -i 's/1.5/1.6/g' build.xml # hack to allow compiling
    ant
    chmod +x bin/fastqc
    ln -s $GAX_REPOS/FastQC/bin/fastqc $GAX_PREFIX/bin/fastqc
fi

## Trim Galore
if ! command -v trim_galore; then
    cd $GAX_REPOS
    curl -fsSL https://github.com/FelixKrueger/TrimGalore/archive/0.4.5.tar.gz -o trim_galore.tar.gz
    tar xvzf trim_galore.tar.gz
    rm trim_galore.tar.gz
    if [[ -v VSC_HOME ]]; then
	wrapprogram $GAX_REPOS/TrimGalore-0.4.5/trim_galore fastqc nopurge
    else
	ln -s $GAX_REPOS/TrimGalore-0.4.5/trim_galore $GAX_PREFIX/bin/trim_galore
    fi
fi

## bowtie2
if ! command -v bowtie2; then
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
if ! command -v STAR; then
    cd $GAX_REPOS
    wget https://github.com/alexdobin/STAR/archive/2.6.1d.tar.gz
    tar -xzf 2.6.1d.tar.gz
    if [[ $OSTYPE == *"darwin"* ]]; then
	ln -s $GAX_REPOS/STAR-2.6.1d/bin/MacOSX_x86_64/STAR $GAX_PREFIX/bin/STAR
    else
	ln -s $GAX_REPOS/STAR-2.6.1d/bin/Linux_x86_64_static/STAR $GAX_PREFIX/bin/STAR
    fi
fi

## SPAdes
#http://cab.spbu.ru/files/release3.12.0/manual.html
if ! command -v spades.py; then
    cd $GAX_REPOS
    wget http://cab.spbu.ru/files/release3.12.0/SPAdes-3.12.0-Linux.tar.gz
    tar -xzf SPAdes-3.12.0-Linux.tar.gz
    rm SPAdes-3.12.0-Linux.tar.gz
    ln -s $GAX_REPOS/SPAdes-3.12.0-Linux/bin/spades.py $GAX_PREFIX/bin/spades.py
fi

## Quality control tools
### BamQC
if ! command -v bamqc; then
    cd $GAX_REPOS
    git clone https://github.com/s-andrews/BamQC.git && cd BamQC
    if [[ -v VSC_HOME ]]; then
	module load ant
    fi
    ant
    chmod 755 bin/bamqc
    ln -s $GAX_REPOS/BamQC/bin/bamqc $GAX_PREFIX/bin/bamqc
fi

### samstat
if ! command -v samstat; then
    cd $GAX_REPOS
    wget https://downloads.sourceforge.net/project/samstat/samstat-1.5.1.tar.gz
    tar -zxf samstat-1.5.1.tar.gz && rm samstat-1.5.1.tar.gz && cd samstat-1.5.1
    ./configure
    make
    ln -s $GAX_REPOS/samstat-1.5.1/src/samstat $GAX_PREFIX/bin/samstat
fi

### RSeQC #=> TODO not fully operational yet, is not possible to symbolically link executable
#### download gene models (further info: https://sourceforge.net/projects/rseqc/files/BED/Human_Homo_sapiens/)
if false; then
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
fi

## RSEM
if ! command -v rsem-calculate-expression; then
    cd $GAX_REPOS
    git clone https://github.com/deweylab/RSEM.git && cd RSEM && make
    if [[ -v VSC_HOME ]]; then
	wrapprogram $GAX_REPOS/RSEM/rsem-prepare-reference Perl
	wrapprogram $GAX_REPOS/RSEM/rsem-calculate-expression Perl
    else
	ln -s $GAX_REPOS/RSEM/rsem-prepare-reference $GAX_PREFIX/bin/rsem-prepare-reference
	ln -s $GAX_REPOS/RSEM/rsem-calculate-expression $GAX_PREFIX/bin/rsem-calculate-expression
    fi
fi

## bedtools
if ! command -v bedtools; then
    cd $GAX_REPOS
    wget https://github.com/arq5x/bedtools2/releases/download/v2.25.0/bedtools-2.25.0.tar.gz
    tar -zxvf bedtools-2.25.0.tar.gz
    cd bedtools2 && make
    for program in $(ls bin); do
	ln -s $GAX_REPOS/bedtools2/bin/$program $GAX_PREFIX/bin/$program
    done
fi

## MACS2
if ! command -v macs2; then
    virtualenv --python=python2.7 $GAX_ENVS/macs2_env
    PYTHONPATH= $GAX_ENVS/macs2_env/bin/pip install numpy --prefix=$GAX_ENVS/macs2_env
    PYTHONPATH= $GAX_ENVS/macs2_env/bin/pip install MACS2 --prefix=$GAX_ENVS/macs2_env
    ln -s $GAX_ENVS/macs2_env/bin/macs2 $GAX_PREFIX/bin/macs2
fi

## deeptools
if ! command -v bamCoverage; then
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
fi

## homer
if ! command -v findPeaks; then
    cd $GAX_REPOS
    mkdir homer && cd homer
    wget http://homer.ucsd.edu/homer/configureHomer.pl
    perl configureHomer.pl -install homer
    ln -s $GAX_REPOS/homer/bin/makeTagDirectory $GAX_PREFIX/bin/makeTagDirectory
    ln -s $GAX_REPOS/homer/bin/findPeaks $GAX_PREFIX/bin/findPeaks
    ln -s $GAX_REPOS/homer/bin/pos2bed.pl $GAX_PREFIX/bin/pos2bed.pl
fi

## freebayes
if ! command -v freebayes; then
    cd $GAX_REPOS
    git clone --recursive https://github.com/ekg/freebayes.git && cd freebayes
    make
    ln -s $GAX_REPOS/freebayes/bin/freebayes $GAX_PREFIX/bin/freebayes
    ln -s $GAX_REPOS/freebayes/bin/bamleftalign $GAX_PREFIX/bin/bamleftalign
fi
