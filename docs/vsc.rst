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

Once you are logged in, go to the `Edit Account` section.

.. image:: /images/vsc/vsc_edit_account.png

At the bottom of the screen you can upload the key that you made
earlier with `ssh-keygen`.

.. image:: /images/vsc/vsc_edit_account.png
.. image:: /images/vsc/vsc_upload_key2.png

To reach the `.ssh` folder where you can find the file to select
(`id_rsa.pub`) type `CMD-SHIFT-G` and fill in `~/.ssh`.

When you have uploaded the key, you should receive a mail that your
account will be activated. You should also be notified of your unique
vsc id number `vscXXXX`. In the following, whenever `vscXXXX` is
written, replace it with your own number.

Prepare your work environment
=============================

Open a terminal, or continue to work in one already opened. And
execute the following lines one by one.

.. code-block: sh

   ssh vscXXX@gengar.ugent.be
   wget -O ~/.bashrc https://raw.githubusercontent.com/dicaso/genairics/master/genairics/scripts/gax_bash_vsc.sh
   source ~/.bashrc
   mkdir -p $GAX_RESOURCES/repos $GAX_DATADIR $GAX_RESULTSDIR
   module load pandas
   pip install --user genairics
   genairics -h

If all went well, the last line gives you the genairics help
output. You are now ready to start and use genairics.
   
Optional: ssh config
====================

TODO: (sshconfig -> ssh vsc)

Basespace api key
=================

* python

* module load pandas
pip3 install --upgrade --user genairics



Submit job to different cluster
===============================

Example submit on golett.

1. Find out server name

.. code-block:: sh

		module swap cluster/golett
		qstat -q
		QSERVER=master19.golett.gent.vsc
		module swap cluster/delcatty

2. Submit job with queue argument --cluster-Q

    genairics --job-launcher qsub --cluster-Q @master19.golett.gent.vsc --remote-host vsc ATACseq NSQ_Run240
