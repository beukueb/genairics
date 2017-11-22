#!/bin/env python
#PBS -N RNAseqPipeline
#PBS -l nodes=1:ppn=16
#PBS -l walltime=72:00:00
#PBS -m be
"""
Full pipeline starting from BaseSpace fastq project
"""
from airflow import DAG
from airflow.operators.bash_operator import BashOperator, python_operator
from datetime import datetime, timedelta
import os

## Tasks
basespaceData = BashOperator(
    task_id='basespace_data',
    bash_command='''
sleep 60
cd {{ params.datadir }}
BaseSpaceRunDownloader.py -p {{ params.NSQrun }} -a $BASESPACE_API_TOKEN
''',
)

qualityCheck = BashOperator(
    task_id='check_quality',
    bash_command='qualitycheck.sh {{ params.NSQrun }} {{ params.dirstructure }} {{ params.datadir }}'
)

alignTask = BashOperator(
    task_id='align_reads',
    bash_command='STARaligning.sh {{ params.NSQrun }} {{ params.dirstructure }} {{ params.datadir }} {{ params.suffix }} {{ params.genome }}'
)

countTask = BashOperator(
    task_id='count_reads',
    bash_command='STARaligning.sh {{ params.NSQrun }} {{ params.datadir }} {{ params.genome }} {{ params.forwardprob }} {{ params.PEND }}'
)

diffexpTask = BashOperator(
    task_id='differential_expression',
    bash_command='simpleDEvoom.R {{ params.NSQrun }} {{ params.datadir }} {{ params.design }}'
)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='RNAseq processing pipeline.')
    # if arguments are set in environment, they are used as the argument default values
    # this allows seemless integration with PBS jobs
    parser.add_argument('datadir', type=str, help='directory that contains data in project folders')
    parser.add_argument('NSQrun', type=str, help='project name')
    parser.add_argument('--dirstructure', type=str, default=os.environ.get('dirstructure','multidir'),
                        help='dirstructure of datatdir: onedir or multidir')
    parser.add_argument('--genome', type=str, default=os.environ.get('genome','RSEMgenomeGRCg38/human_ensembl') ,
                        help='reference genome to use')
    parser.add_argument('--suffix', type=str, default=os.environ.get('suffix',None),
                        help='use when preparing for xenome filtering')
    parser.add_argument('--forwardprob', type=float, default=float(os.environ.get('forwardprob',0.5)),
                        help='stranded seguencing [0 for illumina stranded], or non stranded [0.5]')
    parser.add_argument('--PEND', action='store_true', help='paired end sequencing reads')
    parser.add_argument('--design', type=str, default=os.environ.get('design',None),
                        help='model design for differential expression analysis')

    if os.environ.get('PBS_JOBNAME'):
        #Retrieve arguments from qsub job environment
        #For testing:
        # os.environ.setdefault('datadir','testdir')
        # os.environ.setdefault('NSQrun','testrun')
        args = parser.parse_args('{} {} {}'.format(
            os.environ.get('datadir'),
            os.environ.get('NSQrun'),
            '--PEND ' if os.environ.get('PEND') else '',
        ).split())
    else:
        #Script started directly
        args = parser.parse_args()

    # Set up DAG
    default_args = {
        'owner': os.environ.get('USER','airflow'),
        'depends_on_past': False,
        #'start_date': datetime(2017, 9, 1),
        'email': ['christophe.vanneste@ugent.be'],
        'email_on_failure': False,
        'email_on_retry': False,
        'retries': 1,
        'retry_delay': timedelta(minutes=5),
        # 'queue': 'bash_queue',
        # 'pool': 'backfill',
        # 'priority_weight': 10,
        # 'end_date': datetime(2016, 1, 1),
    }

    # CLI options for pipeline are passed through params
    dag = DAG('RNAseq', start_date = datetime(2017, 9, 1), default_args = default_args, schedule_interval=timedelta(1), params = vars(args))

    dag >> qualityCheck >> alignTask >> countTask #>> diffexpTask
    dag.run()
