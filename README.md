# genairics
GENeric AIRtight omICS pipelines

## Prepare your HPC account
### Get your BASESPACE_API_TOKEN accessToken

Folow the steps 1-5 from this link:
https://help.basespace.illumina.com/articles/tutorials/using-the-python-run-downloader/

### add to your HPC ~/.bashrc =>

    if [[ -v SET_LUIGI_FRIENDLY ]]; then module load pandas; unset SET_LUIGI_FRIENDLY; fi
    if [[ -v R_MODULE ]]; then module purge; module load R-bundle-Bioconductor; unset R_MODULE; fi
    export PATH=$VSC_DATA_VO/resources/bin:$PATH
    export BASESPACE_API_TOKEN= #Set this to your basespace api token

### Execute the following commands

    module load pandas
    pip3 install --user luigi

## Example run

   qsub -l walltime=10:50:00 -l nodes=1:ppn=12 -m n \
   -v project=2016_BRIP1kd_SVH,NSQrun=NSQ_Run212,datadir=$VSC_DATA_VO_USER/data,forwardprob=0,SET_LUIGI_FRIENDLY=,GENAIRICS_ENV_ARGS= \
   $VSC_DATA_VO/resources/repos/genairics/genairics/RNAseq.py
   
## General setup for vo admin

    cd $VSC_DATA_VO/resources/bin
    ln -s ../repos/qsub_scripts/qualitycheck.sh qualitycheck.sh
    ln -s ../repos/qsub_scripts/STARaligning.sh STARaligning.sh
    ln -s ../repos/qsub_scripts/RSEMcounts.sh RSEMcounts.sh

## Development

### Interactive node for debugging

    qsub -I -l walltime=09:50:00 -l nodes=1:ppn=12

### Debug job

    qsub -q debug -l walltime=00:50:00 -l nodes=1:ppn=4 -m n \
    -v datadir=$VSC_DATA_VO_USER/data,NSQrun=NSQ_Run270,forwardprob=0,SET_LUIGI_FRIENDLY=,GENAIRICS_ENV_ARGS= \
    $VSC_DATA_VO/resources/repos/genairics/genairics/RNAseq.py