#!/bin/bash
set -x #Get all debugging info

# Installs all dependencies for genairics to run its pipelines
cd $REPOS

## fastqc -> installed with apt-get

## STAR
wget https://github.com/alexdobin/STAR/archive/2.5.3a.tar.gz
tar -xzf 2.5.3a.tar.gz
ln -s $REPOS/STAR-2.5.3a/bin/Linux_x86_64_static/STAR $PREFIX/bin/STAR

## RSEM
git clone https://github.com/deweylab/RSEM.git
cd RSEM
make
cd ..
ln -s $REPOS/RSEM/rsem-prepare-reference $PREFIX/bin/rsem-prepare-reference
ln -s $REPOS/RSEM/rsem-calculate-expression $PREFIX/bin/rsem-calculate-expression
