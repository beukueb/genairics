#!/ur/bin/env python
# PYTHON_ARGCOMPLETE_OK
import os, sys

def prepareParser():
    """
    Prepares the argument parser, joblaunchers and pipelines for genairics
    hooks up the different pipelines that are made available through the CLI
    returns (parser, joblaunchers, pipelines)
    """
    import argparse
    from collections import OrderedDict
    from genairics import typeMapping, config
    from genairics.jobs import QueuJob, SlurmJob
    from genairics.RNAseq import RNAseq
    from genairics.ChIPseq import ChIPseq
    from genairics.ATACseq import ATACseq

    pipex = os.environ.get('GAX_PIPEX')
    if pipex:
        import importlib
        pipem = importlib.import_module(pipex[:pipex.rindex('.')])
        pipef = vars(pipem)[pipex[pipex.rindex('.')+1:]]
        external_pipeline = ((pipex[pipex.rindex('.')+1:],pipef),)
    else:
        external_pipeline = ()
    
    pipelines = OrderedDict(external_pipeline+(
        ('RNAseq',RNAseq),
        ('ChIPseq',ChIPseq),
        ('ATACseq',ATACseq)
    ))

    joblaunchers = OrderedDict((
        ('native', None),
        ('qsub', QueuJob),
        ('slurm', SlurmJob)
    ))
    
    parser = argparse.ArgumentParser(
        prog = 'genairics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=r'''
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

    GENeric AIRtight omICS pipeline.

    When the program is finished running, you can check the log file with "less -r plumbing/pipeline.log"
    from your project's result directory. Errors will also be printed to stdout.
    ''')

    parser.add_argument('--job-launcher', default = 'native', type = str, choices = joblaunchers.keys(),
                        help='choose where and how the job will run')
    parser.add_argument('--cluster-Q', default = '', type = str,
                        help = 'the queue and/or job cluster to which job will be submitted. Format should be qname@clusterservername')
    parser.add_argument('--cluster-PPN', default = config.threads, type = int,
                        help = '''Number of processors per node that will be requested 
(recommended > 12) (default: {})'''.format(config.threads))
    parser.add_argument('--remote-host', default = '', type = str, help = 'submit job through ssh')
    parser.add_argument('--save-config', action = 'store_true',
                        help = 'save path related default values to a configuration file in the directory where you started genairics')
    parser.add_argument('--debug', action = 'store_true', help = 'Return console with pipeline in environment for debugging')
    parser.add_argument('--verbose', action = 'store_true', help = 'verbose output')

    # Pipeline subparsers
    subparsers = parser.add_subparsers(help='sub-command help')
    for pipeline in pipelines:
        subparser = subparsers.add_parser(
            pipeline,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            help='genairics {} -h'.format(pipeline)
        )
        subparser.set_defaults(function=pipelines[pipeline])
        for paran,param in pipelines[pipeline].get_params():
            if type(param._default) in typeMapping.values():
                if typeMapping[type(param)] is bool: #CLI flag
                    subparser.add_argument(
                        '--'+paran, action='store_false' if param._default else 'store_true',
                        help=param.description+' (no argument needed)'
                    )
                else: #CLI argument with value
                    subparser.add_argument(
                        '--'+paran, default=param._default,
                        type=typeMapping[type(param)], help=param.description
                    )
            else: subparser.add_argument(paran, type=typeMapping[type(param)], help=param.description)

    # Console option
    def startConsole():
        import IPython
        import genairics as gax
        import genairics, genairics.datasources, genairics.resources, genairics.RNAseq
        from genairics.resources import InstallDependencies
        IPython.embed()
        exit()
        
    subparser = subparsers.add_parser(
        'console',
        help='Start console where tasks can be started not available in the commandline interface'
    )
    subparser.set_defaults(function=startConsole)

    return parser, joblaunchers, pipelines

def main(args=None):
    """
    Checks where arguments are provided (directly to main function, environment, CLI),
    parses them and starts the workflow.
    """
    import argcomplete, os, logging
    from genairics import config, typeMapping, logger, runWorkflow

    parser, joblaunchers, pipelines = prepareParser()
    
    if args is None:
        # if arguments are set in environment, they are used as the argument default values
        # but only when no other arguments are passed on the command line
        # this allows seemless integration with PBS jobs
        if len(sys.argv) == 1 and 'GENAIRICS_ENV_ARGS' in os.environ:
            #Retrieve arguments from qsub job environment
            args = [os.environ['GENAIRICS_ENV_ARGS']]
            positionals = []
            optionals = []
            for paran,param in pipelines[args[0]].get_params():
                if paran in os.environ:
                    if isinstance(param._default,bool):
                        # bool flags should only be present in environ when set (value not checked)
                        optionals += ['--'+paran]
                    elif type(param._default) in typeMapping.values():
                        optionals += ['--'+paran, os.environ[paran]]
                    else: positionals.append(os.environ[paran])
            logger.warning(
                'Pipeline %s arguments were retrieved from environment: positional %s, optional %s',
                args[0], positionals, optionals
            )
            args+= optionals + positionals
            args = parser.parse_args(args)
        #normal cli
        else:
            #Script started directly
            argcomplete.autocomplete(parser)
            args = parser.parse_args()
    else: args = parser.parse_args(args) # args passed to main function directly
    
    #Make dict out of args namespace for passing to pipeline
    args = vars(args)

    # First check if it was requested to save config
    if args.pop('save_config'):
        from genairics import saveConfig
        for param in config.get_param_names():
            if param in args:
                config.__setattr__(param, args[param])
        saveConfig(config)
        
    # Extract other non pipeline specific arguments
    joblauncher = joblaunchers[args.pop('job_launcher')]
    remotehost = args.pop('remote_host')
    clusterQ = args.pop('cluster_Q')
    clusterPPN = args.pop('cluster_PPN')
    verbose = args.pop('verbose')
    debug = args.pop('debug')
    workflow = args.pop('function')(**args)

    if verbose:
        logger.setLevel(logging.DEBUG)
    else: logger.setLevel(logging.INFO)
    
    if debug:
        import IPython
        from plumbum import colors
        todos = workflow.debug_requirements()
        print(
            colors.red | 'Debug mode.',
            'Uncompleted tasks for {}'.format(workflow),
            'can be found in the generator variable `todos`.',
            'To see the first uncompleted task in line:',
            colors.green | '>>> next(todos)',
            sep = '\n'
        )
        IPython.embed()
        exit()
    elif joblauncher:
        logger.debug('submitting %s to %s',workflow,joblauncher)
        joblauncher(
            job=workflow,remote=remotehost,
            clusterQ=clusterQ,clusterPPN=clusterPPN
        ).run()
    else: runWorkflow(workflow,verbose=verbose)

# Run main program logics when script called directly
if __name__ == "__main__":
    main()
