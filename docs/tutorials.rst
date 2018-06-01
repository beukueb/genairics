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
