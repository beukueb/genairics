#!/bin/bash
set -x #Get all debugging info

# Installs all dependencies for genairics to run its pipelines
cd $REPOS

## Basespace downloader
wget https://da1s119xsxmu0.cloudfront.net/sites/knowledgebase/API/08052014/Script/BaseSpaceRunDownloader_v2.zip
unzip BaseSpaceRunDownloader_v2.zip
#make it run with python2 by inserting shebang at first line
sed -i '1s@^@#!/usr/bin/env python2\n@' BaseSpaceRunDownloader_v2.py
chmod +x BaseSpaceRunDownloader_v2.py
ln -s $REPOS/BaseSpaceRunDownloader_v2.py $PREFIX/bin/BaseSpaceRunDownloader.py

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
