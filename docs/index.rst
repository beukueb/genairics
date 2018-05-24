.. genairics documentation master file, created by
   sphinx-quickstart on Fri Mar 30 08:47:45 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to genairics's documentation!
=====================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


  
Module documentation
====================
.. automodule:: genairics
   :members:

Tutorials
=========

Downloading and preparing index manually
----------------------------------------

    $ ssh vsc
    $ screen -D -R
    $ qsub -I -l walltime=10:00:00 -l nodes=1:ppn=4
    $ module load pandas
    $ genairics console
    >>> gax.resources.RetrieveGenome(genome='mus_musculus',release=91).run()
    >>> gax.resources.Bowtie2Index(genome='mus_musculus',release=91).run()
