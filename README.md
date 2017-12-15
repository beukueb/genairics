```
      _______
      -------
         |||
      /+++++++:         __-_-_-_-_
  /#-'genairics'-,_     /;@;@,@'@+`
 /##@+;+++++++:@.+#\\/`,@@;@;@;@`@'\
 :#@:'###    #+';.#'\\@@'#####++;:@+
 |#@`:,:      #+#:+#+\\+#     #+@@++|
 ;@'.##         '+.:#_\\       #+@,`:
 :#@;.#         |+;,| ||        ##@`.|
 |@'..#         \\###-;|         #@:.:
 |#@;:#        '+\\::/\:         +#@::
 :@;,:+       #@@'\\/ ,\        #';@.|
 \#@'#'#     #'@',##;:@`        ##@,;;
  :##@:@:@;@;@;@.;/  \#+@;#` #'#+@`:;
  `\#.@;@;@;@:@.+/    :'@;@;@;@;@,:;
     \,,'::,,#::;      \'@:@'@;@'+'/

GENeric AIRtight omICS pipelines
```

## Disclosure

There comes a point in time when any human just has to develop their
own, fully-fledged computational genomics platform. This is not that
time for me, but it is good to set it as an aim: aiming for the stars,
landing somewhere on the moon.

### Design goals

#### generic pipelines

Although the pipelines here available are only developed for my
specific bioinformatics needs and that of my collaborators, they are
build up in a generic way, and some of the functionality in the main
genairics package file might help or inspire you to build your own
pipelines. The core of the pipelines is build with
[luigi](https://luigi.readthedocs.io) and extensions are provided in
this package's initialization file.

#### airtight pipelines

The pipelines are build so they can be started with a single,
fool-proof command.  This should allow my collaborators, or scientists
wanting to replicate my results, to easily do so. A
docker container is provided with the package so the processing
can be started up on any platform.

#### omics pipelines

The pipelines grow organically, as my research needs expand. I aim to
process any kind of data. If you want to use my set of pipelines, but
desire an expansion to make it more omics-like, contact me and we can
see if there are opportunities to collaborate. More generally,
everyone is welcome to leave suggestions in the [issues
section](https://github.com/beukueb/genairics/issues) of the
repository.

## Installation
### Prepare your HPC account
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
    pip3 install --user luigi plumbum openpyxl matplotlib
    mkdir $VSC_DATA_VO_USER/{data,results}

## Example run

   qsub -l walltime=10:50:00 -l nodes=1:ppn=12 -m n \
   -v project=2016_BRIP1kd_SVH,NSQrun=NSQ_Run212,datadir=$VSC_DATA_VO_USER/data,forwardprob=0,SET_LUIGI_FRIENDLY=,GENAIRICS_ENV_ARGS= \
   $VSC_DATA_VO/resources/repos/genairics/genairics/RNAseq.py
   
## General setup for vo admin

    cd $VSC_DATA_VO/resources/bin
    ln -s ../repos/qsub_scripts/qualitycheck.sh qualitycheck.sh
    ln -s ../repos/qsub_scripts/STARaligning.sh STARaligning.sh
    ln -s ../repos/qsub_scripts/RSEMcounts.sh RSEMcounts.sh
    ln -s ../repos/genairics/scripts/simpleDEvoom.R simpleDEvoom.R
    ln -s ../repos/genairics/genairics/RNAseq.py RNAseq.py

## Development

### Interactive node for debugging

    qsub -I -l walltime=09:50:00 -l nodes=1:ppn=12

### Debug job

    qsub -q debug -l walltime=00:50:00 -l nodes=1:ppn=4 -m n \
    -v datadir=$VSC_DATA_VO_USER/data,project=NSQ_Run270,forwardprob=0,SET_LUIGI_FRIENDLY=,GENAIRICS_ENV_ARGS= \
    $VSC_DATA_VO/resources/repos/genairics/genairics/RNAseq.py

### Running container

    . ~/.BASESPACE_API
    docker run -v /Users/cvneste/mnt/vsc/resources:/resources \
               -v /Users/cvneste/mnt/vsc/vsc40603/data:/data \
	       -v /Users/cvneste/mnt/vsc/vsc40603/results:/results \
	       --env-file ~/.BASESPACE_API \
	       8ab716d0a38f RNAseq --project 2016_BRIP1kd_SVH --datadir /data --forwardprob 0