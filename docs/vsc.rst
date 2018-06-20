Using genairics on UGent HPC
----------------------------

Request account
===============

* sshconfig -> ssh vsc


mkdir data results

Basespace api key
=================

* cp $VSC_DATA_VO/resources/template.bashrc ~/.bashrc
  
* python

* module load pandas
pip3 install --upgrade --user genairics



Submit job to different cluster
===============================

Example submit on golett.

1. Find out server name
   
    module swap cluster/golett
    qstat -q
    QSERVER=master19.golett.gent.vsc
    module swap cluster/delcatty

2. Submit job with queue argument --cluster-Q

    genairics --job-launcher qsub --cluster-Q @master19.golett.gent.vsc --remote-host vsc ATACseq NSQ_Run240
