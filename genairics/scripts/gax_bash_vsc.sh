# bashrc script that can be used as template for UGent VSC/HPC environment

# enable color support of ls and also add handy aliases
if [ -x /usr/bin/dircolors ]; then
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    alias grep='grep --color=auto'
    alias fgrep='fgrep --color=auto'
    alias egrep='egrep --color=auto'
fi

#Use colors
force_color_prompt=yes

if [ -n "$force_color_prompt" ]; then
    if [ -x /usr/bin/tput ] && tput setaf 1 >&/dev/null; then
    color_prompt=yes
else
  	color_prompt=
fi
fi
if [ "$color_prompt" = yes ]; then
   PS1='${debian_chroot:+($debian_chroot)}\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
else
   PS1='${debian_chroot:+($debian_chroot)}\u@\h:\w\$ '
fi

unset color_prompt force_color_prompt

if [ -z $BASH_PATHS_SET ]
then
    export BASH_PATHS_SET=yes
    export PATH=$VSC_DATA_VO/resources/bin:$VSC_DATA/bin:$PATH:~/.local/bin
    export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/user/home/gent/vsc406/vsc40603/programs/zeromq-3.2.2/bin/lib
    #export PYTHONPATH=${PYTHONPATH}:
    export VOU=$VSC_DATA_VO_USER
fi

alias emacs='emacs -Q'

# Genairics env
export GAX_RESOURCES=${VSC_DATA_VO:-$VSC_DATA}/resources
export GAX_REPOS=$GAX_RESOURCES/repos
export GAX_PREFIX=$GAX_RESOURCES
export GAX_DATADIR=${VSC_DATA_VO:-$VSC_DATA}/data
export GAX_RESULTSDIR=${VSC_DATA_VO:-$VSC_DATA}/results

if [ ! -d "$GAX_RESOURCES" ]; then
    echo GAX_RESOURCES directory does not exist, please execute the following line:
    echo mkdir -p $GAX_RESOURCES
fi
if [ ! -d "$GAX_DATADIR" ]; then
    echo GAX_DATADIR directory does not exist, please execute the following line:
    echo mkdir -p $GAX_DATADIR $GAX_RESULTSDIR
fi

if [[ -v SET_LUIGI_FRIENDLY ]]; then module load pandas; unset SET_LUIGI_FRIENDLY; fi

# TODO use the wrapperscript functionality and remove these settings here
if [[ -v R_MODULE ]]; then module purge; module load R-bundle-Bioconductor; unset R_MODULE; fi
if [[ -v MACS2_MODULE ]]; then module purge; module load MACS2; unset MACS2_MODULE; fi
if [[ -v DEEPTOOLS_MODULE ]]; then module purge; module load deepTools; unset DEEPTOOLS_MODULE; fi
