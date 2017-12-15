#!/ur/bin/env python

def main(args=None):
    import argparse
    from collections import OrderedDict
    from genairics import typeMapping, logger, runWorkflow
    from genairics.RNAseq import RNAseqWorkflow
    from genairics.ChIPseq import fastqcSample

    pipelines = OrderedDict((
        ('RNAseq',RNAseqWorkflow),
        ('ChIPseq',fastqcSample)
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
    
    subparsers = parser.add_subparsers(help='sub-command help')
    for pipeline in pipelines:
        subparser = subparsers.add_parser(
            pipeline,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            help='{} help'.format(pipeline)
        )
        subparser.set_defaults(function=pipelines[pipeline])
        for paran,param in pipelines[pipeline].get_params():
            if type(param._default) in typeMapping.values():
                subparser.add_argument('--'+paran, default=param._default, type=typeMapping[type(param)],
                                       help=param.description)
            else: subparser.add_argument(paran, type=typeMapping[type(param)], help=param.description)
        
    if args is None:
        args = parser.parse_args()
        args = vars(args)

    workflow = args.pop('function')(**args)
    runWorkflow(workflow)

if __name__ == "__main__":
    main()
