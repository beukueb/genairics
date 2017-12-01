# genairics
GENeric AIRtight omICS pipelines

## Prepare your HPC account
### add to your ~/.bashrc =>

    if [[ -v SET_LUIGI_FRIENDLY ]]; then module load pandas; unset SET_LUIGI_FRIENDLY; fi
    export PATH=$VSC_DATA_VO/resources/bin:$PATH

## General setup for vo admin

    cd $VSC_DATA_VO/resources/bin
    ln -s ../repos/qsub_scripts/qualitycheck.sh qualitycheck.sh
    ln -s ../repos/qsub_scripts/STARaligning.sh STARaligning.sh
    ln -s ../repos/qsub_scripts/RSEMcounts.sh RSEMcounts.sh

## Development

### Interactive node for debugging

    qsub -I -l walltime=09:50:00 -l nodes=1:ppn=12

### Debug job

    qsub -q debug -l walltime=00:50:00 -l nodes=1:ppn=4 -v DATADIR=$VSC_DATA_VO_USER/data,NSQrun=NSQ_Run270,FORWARDPROB=0,SET_LUIGI_FRIENDLY=,GENAIRICS_ENV_ARGS= $VSC_DATA_VO/resources/repos/genairics/genairics/RNAseq.py