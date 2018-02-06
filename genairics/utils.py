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

def dict2argparsed(argparsedict,typecheck=False,plumbumCommand=True):
    """
    takes a arg dict and constructs the argparsed commandline 
    as a pumblum command ready for execution
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
    if plumbumCommand:
        return command.bound_command(*cli_arguments)
    else: return cli_arguments

def webserver(parser,queue,jobstatus,stopevent):
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

    @app.route('/stopserver',methods=['GET'])
    def stopserver():
        stopevent.set()
        if queue.empty(): queue.put((None,None))
        return "Server closing down"
    
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

def startJob(queue,jobstatus,stopevent):
    """
    Starts the jobs.
    To stop, stopevent needs to be set to true and
    an item needs to be put on the queue incase it is 
    empty, as the thread will otherwise hang waiting
    for another job.
    """
    from genairics import logger
    from genairics.__main__ import main
    while True:
        jobid,job = queue.get()
        if stopevent.is_set(): break
        jobstatus[jobid] = "started"
        stdout = job() # when the queue provides ready jobs
        logger.info(stdout)
        #main(job)
        jobstatus[jobid] = "finished"
        
def jobserver(args=None):
    import threading, queue, webbrowser, signal, sys
    from genairics import config, logger
    from genairics.__main__ import prepareParser
    logger.setLevel('DEBUG')

    parser = prepareParser()[0] #parser is first element of tuple returned

    stopevent = threading.Event()
    jobqueue = queue.Queue()
    jobstatus = {}
    threads = {
        'server': threading.Thread(target=webserver, daemon=True, args=(parser,jobqueue,jobstatus,stopevent)),
        'worker': threading.Thread(target=startJob, args=(jobqueue,jobstatus,stopevent))
    }
    for t in threads.values(): t.start()

    # open genairics wui in webbrowser
    if config.browser:
        webbrowser.get(config.browser).open('http://127.0.0.1:5000/',new=2)

    threads['worker'].join()
    #def signal_handler(signal, frame):
    #    print('You pressed Ctrl+C!')
    #    exit(0)
    #signal.signal(signal.SIGINT, signal_handler)
    #print('Press Ctrl+C to exit genairics server')
    #signal.pause()
