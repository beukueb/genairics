#!/bin/bash
set -x #Get all debugging info

# Installs all dependencies for genairics to run its pipelines
cd $REPOS

## Basespace downloader
wget https://da1s119xsxmu0.cloudfront.net/sites/knowledgebase/API/08052014/Script/BaseSpaceRunDownloader_v2.zip
unzip BaseSpaceRunDownloader_v2.zip
