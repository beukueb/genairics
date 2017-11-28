# genairics
Airflow genomics pipelines

## Prepare your HPC account
### add to your ~/.bashrc =>

    export PATH=$VSC_DATA_VO/resources/bin:$PATH

## General setup for vo admin

    cd $VSC_DATA_VO/resources/bin
    ln -s ../repos/qsub_scripts/qualitycheck.sh qualitycheck.sh
    ln -s ../repos/qsub_scripts/STARaligning.sh STARaligning.sh
    ln -s ../repos/qsub_scripts/RSEMcounts.sh RSEMcounts.sh