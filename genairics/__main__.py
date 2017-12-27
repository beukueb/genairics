#!/ur/bin/env python
# PYTHON_ARGCOMPLETE_OK
import os, sys

def main(args=None):
    import argparse, argcomplete, os, logging
    from collections import OrderedDict
    from plumbum import local
    from genairics import gscripts, typeMapping, logger, runWorkflow
    from genairics.jobs import QueuJob
    from genairics.RNAseq import RNAseq
    from genairics.ChIPseq import fastqcSample

    pipelines = OrderedDict((
        ('RNAseq',RNAseq),
        ('ChIPseq',fastqcSample)
    ))

    joblaunchers = OrderedDict((
        ('native', None),
        ('qsub', QueuJob)
    ))
    
    parser = argparse.ArgumentParser(
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

    parser.add_argument('--job-launcher', default = 'native', choices = joblaunchers.keys(),
                        help='choose where and how the job will run')
    parser.add_argument('--remote-host', default = '', help = 'submit job through ssh')
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
                subparser.add_argument('--'+paran, default=param._default, type=typeMapping[type(param)],
                                       help=param.description)
            else: subparser.add_argument(paran, type=typeMapping[type(param)], help=param.description)

    # Console option
    def startConsole():
        import IPython
        import genairics, genairics.datasources, genairics.resources
        from genairics.resources import InstallDependencies
        IPython.embed()
        exit()
        
    subparser = subparsers.add_parser(
        'console',
        help='Start console where tasks can be started not available in the commandline interface'
    )
    subparser.set_defaults(function=startConsole)
    
    if args is None:
        # if arguments are set in environment, they are used as the argument default values
        # this allows seemless integration with PBS jobs
        if 'GENAIRICS_ENV_ARGS' in os.environ:
            #Retrieve arguments from qsub job environment
            args = [os.environ['GENAIRICS_ENV_ARGS']]
            positionals = []
            optionals = []
            for paran,param in pipelines[args[0]].get_params():
                if paran in os.environ:
                    if type(param._default) in typeMapping.values():
                        optionals += ['--'+paran, os.environ[paran]]
                    else: positionals.append(os.environ[paran])
            logger.warning(
                'Pipeline %s arguments were retrieved from environment: positional %s, optional %s',
                args[0], positionals, optionals
            )
            args+= optionals + positionals
            args = parser.parse_args(args)
        else:
            #Script started directly
            argcomplete.autocomplete(parser)
            args = parser.parse_args()
        #Make dict out of args namespace for passing to pipeline
        args = vars(args)

    joblauncher = joblaunchers[args.pop('job_launcher')]
    remotehost = args.pop('remote_host')
    verbose = args.pop('verbose')
    workflow = args.pop('function')(**args)

    if verbose:
        logger.setLevel(logging.DEBUG)
    else: logger.setLevel(logging.INFO)
    
    if joblauncher:
        joblauncher(job=workflow,remote=remotehost).run()
    else: runWorkflow(workflow)

# If only program name is entered generate GUI
if len(sys.argv) == 1:
    from gooey import Gooey
    main = Gooey(
        advanced=True,
        program_description='genairics: generic airtight omics pipelines'
    )(main)
    # Disable stdout buffering so gooey has smooth output
    nonbuffered_stdout = os.fdopen(sys.stdout.fileno(), 'w', 1)
    sys.stdout = nonbuffered_stdout

# Run main program logics when script called directly
if __name__ == "__main__":
    main()
