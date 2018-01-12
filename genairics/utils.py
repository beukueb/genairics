#!/usr/bin/env python
import json
from collections import OrderedDict

def argparser2dict(parser,arguments = None, indent = False):
    """
    Returns a dict with key prog name
    and value a list of the expected arguments.

    Subparser arg groups are in sublists and can thus be recognised when the
    value of a key is a list and not a dict.

    The dict should be transformable with json.dump[s]
    """
    import argparse
    if arguments is None:
        arguments = []
        returnFinalDict = True
    else: returnFinalDict = False
    for action in parser._actions:
        if type(action) is argparse._SubParsersAction:
            for subparser in action.choices:
                if subparser not in argparser2dict.filter:
                    arguments.append({'name':subparser,'type':'subparser','value':None,'args':[]})
                    argparser2dict(action.choices[subparser],arguments[-1]['args'])
        elif action.dest not in argparser2dict.filter:
            arg = vars(action).copy()
            arg['name'] = arg.pop('dest')
            arg['positional'] = False if arg['option_strings'] else True
            arg['type'] = argparser2dict.typeDict[arg.pop('type')]
            arg['choices'] = list(action.choices) if action.choices else None
            arg['value'] = None
            if arg['default'] is None: arg['default'] = ''
            arg.pop('container')
            arguments.append(arg)
    if returnFinalDict:
        return {parser.prog:arguments}
argparser2dict.typeDict = {
    bool: 'checkbox',
    int: 'number',
    float: 'number',
    str: 'text',
    None: 'checkbox'
    # store_true does not have a type set on the argument element (TODO documentation!), only for general genairics options not luigi derived args
}
argparser2dict.filter = {'help','console','server'}

def dict2argparsed(argparsedict,typecheck=False):
    """
    takes a arg dict and constructs the argparsed commandline 
    as a pumblum command ready for execution

    values are optionally typechecked (NOT YET)

    WORK IN PROGRESS!
    """
    from plumbum import local
    def recursive_args(arguments,cli_arguments):
        for arg in arguments:
            if arg['type'] == 'subparser':
                if arg['value'] == 'set':
                    cli_arguments.append(arg['name'])
                    recursive_args(arg['args'],cli_arguments)
            else:
                if arg['positional']:
                    cli_arguments.append(arg['value'])
                elif arg['const'] and arg['value']:
                    cli_arguments.append(arg['option_strings'][0])
                elif arg['value']: cli_arguments += [arg['option_strings'][0],arg['value']]
    arguments = argparsedict
    for prog in arguments:
        command = local[prog]
        cli_arguments = []
        recursive_args(arguments[prog],cli_arguments)
    return command.bound_command(*cli_arguments)

dict2argparsed.inputDict = {
    v:k for k,v in argparser2dict.typeDict.items() if k and k != int
} # float and int are taken together, None is not considered

def webserver(parser,queue=None,jobstatus=None):
    from flask import Flask, request, render_template
    app = Flask('genairics')

    @app.route('/')
    def offerJob():
        jobargs = argparser2dict(parser)
        return render_template('index.html',jobargs=jobargs)

    @app.route('/checkstatus',methods=['GET','POST'])
    def checkJobStatus():
        if request.json:
            data = request.json
            app.logger.debug("checking %s",data)
            try:
                return jobstatus[data["id"]]
            except KeyError:
                return "unknown (job submitted previously)"
    
    @app.route('/submitjob',methods=['GET','POST'])
    def takeJSONjob():
        app.logger.info("genairics job submitted")
        app.logger.debug(request.json)
    
        if request.json:
            data = request.json
            jobargs = argparser2dict(parser)
            for prog in jobargs:
                for arg in jobargs[prog]:
                    if arg['type'] == 'subparser':
                        if arg['name'] == data['pipeline']:
                            arg['value'] = 'set'
                            for subarg in arg['args']:
                                try: subarg['value'] = data[subarg['name']]
                                except KeyError: app.logger.warning('pipeline option %s not set',subarg['name'])
                    else:
                        try: arg['value'] = data[arg['name']]
                        except KeyError: app.logger.warning('global option %s not set',arg['name'])
            command = dict2argparsed(jobargs)
            if queue: queue.put((data.get("jobid"),command))
            return "Job %s submitted" % data.get("jobid")

        else:
            return "no json job received"

    app.run()

def startJob(queue,jobstatus):
    from genairics import logger
    while True:
        jobid,job = queue.get()
        jobstatus[jobid] = "started"
        stdout = job()
        logger.info(stdout)
        jobstatus[jobid] = "finished"
        
def jobserver(parser):
    import threading, queue, webbrowser, signal, sys
    from genairics import config, logger
    logger.setLevel('DEBUG')

    jobqueue = queue.Queue()
    jobstatus = {}
    threads = {
        'server': threading.Thread(target=webserver, args=(parser,jobqueue,jobstatus)),
        'worker': threading.Thread(target=startJob, args=(jobqueue,jobstatus))
    }
    for t in threads.values(): t.start()

    # open genairics wui in webbrowser
    if config.browser:
        webbrowser.get(config.browser).open('http://127.0.0.1:5000/',new=2)
    
    def signal_handler(signal, frame):
        print('You pressed Ctrl+C!')
        exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    print('Press Ctrl+C to exit genairics server')
    signal.pause()
    
