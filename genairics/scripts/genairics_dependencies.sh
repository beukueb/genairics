#!/bin/bash
set -x #Get all debugging info

# Installs all dependencies for genairics to run its pipelines
mkdir -p $GAX_REPOS && cd $GAX_REPOS

# Enable genairics CLI argument completion
# https://github.com/kislyuk/argcomplete/
activate-global-python-argcomplete

## fastqc -> install with apt-get, brew, ...

## STAR
wget https://github.com/alexdobin/STAR/archive/2.5.3a.tar.gz
tar -xzf 2.5.3a.tar.gz
if [[ $OSTYPE == *"darwin"* ]]; then
    ln -s $GAX_REPOS/STAR-2.5.3a/bin/MacOSX_x86_64/STAR $GAX_PREFIX/bin/STAR
else
    ln -s $GAX_REPOS/STAR-2.5.3a/bin/Linux_x86_64_static/STAR $GAX_PREFIX/bin/STAR
fi

## RSEM
git clone https://github.com/deweylab/RSEM.git
cd RSEM
make
cd ..
ln -s $GAX_REPOS/RSEM/rsem-prepare-reference $GAX_PREFIX/bin/rsem-prepare-reference
ln -s $GAX_REPOS/RSEM/rsem-calculate-expression $GAX_PREFIX/bin/rsem-calculate-expression
