Development
-----------

General setup for sys/vo admin
==============================

Choose a different prefix, if you want dependencies installed in different dir

    git clone https://github.com/beukueb/genairics.git && cd genairics
    PREFIX=$VSC_DATA_VO/resources genairics/scripts/genairics_dependencies.sh

git repo
^^^^^^^^
For new version do `git updatemaster`, which automates working from
dev branch, merging to master and updating version with following
aliases in `.git/config`

	[alias]
	repoversion = !echo 25
	updaterepoversion = !git config --local alias.repoversion '!echo '$(($(git repoversion)+1)) && git repoversion
	updateversion = !sed -i -e 's/version = \".*\"/version = \"0.1.'$(git updaterepoversion)'\"/' setup.py && git commitversion
	commitversion = !git commit -am"subversion=$(git repoversion)"
	tagversion = !git tag -a v0.1.$(git repoversion) -m 'genairics version 0.1.'$(git repoversion) && git push origin v0.1.$(git repoversion)
	updatemaster = !git updateversion && git checkout master && git merge dev && git tagversion && git push origin master && git checkout dev
	pulldev = !git pull origin dev && pip3 install --user --upgrade .

Testing
^^^^^^^

Tests can be run from the repo directory with `python3 setup.py test`. Tests are
included for any pipelines referenced in papers and pipelines used by collaborators.

Mac OS X
^^^^^^^^

Setup
"""""

Install brew: https://docs.brew.sh/Installation.html

    brew install python3 bowtie2
    brew install homebrew/core/fastqc homebrew/science/bedtools
    pip3 install --user genairics

Install fuse from https://osxfuse.github.io/ and sshfs from https://github.com/osxfuse/sshfs/releases

HPC
^^^

Interactive node for debugging
""""""""""""""""""""""""""""""

    qsub -I -l walltime=09:50:00 -l nodes=1:ppn=12

Debug job
"""""""""

    qsub -q debug -l walltime=00:50:00 -l nodes=1:ppn=4 -m n \
    -v datadir=$VSC_DATA_VO_USER/data,project=NSQ_Run270,forwardprob=0,SET_LUIGI_FRIENDLY=,GENAIRICS_ENV_ARGS= \
    $VSC_DATA_VO/resources/repos/genairics/genairics/RNAseq.py

Submit package to pypi
^^^^^^^^^^^^^^^^^^^^^^

    python setup.py sdist upload -r pypi

Docker
^^^^^^

Build container
"""""""""""""""

     #docker build . --build-arg buildtype=development #for development
     docker build . --tag beukueb/genairics:latest
     docker push beukueb/genairics:latest
     docker tag beukueb/genairics:latest genairics

To debug, reset entrypoint:

    docker run -it -v /tmp/data:/data -v /tmp/results:/results -v /Users/cvneste/mnt/vsc/resources:/resources --env-file ~/.BASESPACE_API --entrypoint bash bcaf446c7765

Cleaning docker containers/images
"""""""""""""""""""""""""""""""""

     docker system prune -f

Build distribution package
^^^^^^^^^^^^^^^^^^^^^^^^^^

    workon genairics
    pip install pyinstaller
    pyinstaller --onefile __main__.spec
    dist/genairics/genairics -h

Mac OS X dmg
""""""""""""

    workon genairics
    pushd dist
    hdiutil create ./genairics.dmg -srcfolder genuirics -ov
    popd
