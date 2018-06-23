Using genairics on UGent HPC (instructions for Mac users)
---------------------------------------------------------

Request account
===============

Open a terminal: make the key combination `CMD-space` and type
`terminal`, click on `Terminal` with the black 'terminal' icon.

In the terminal copy paste the following line:

    ssh-keygen

Press enter, and press enter for every question (in total 4x `enter`).
Now you are ready to go and request a vsc account, by clicking on the
following link: `https://account.vscentrum.be/ <https://account.vscentrum.be/>`_.

.. image:: /images/vsc/request_account_startscreen.png

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
