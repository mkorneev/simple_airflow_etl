#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Simple ETL that
* every 15 minutes inserts a new row into a table including the timestamp and a randomised value between 1 and 10
* at the end of every hour sums up the respective values and stores it in a separate table (with timestamp)
"""

import logging
import random
from datetime import datetime, timedelta

from airflow import DAG
from airflow.hooks.sqlite_hook import SqliteHook
from airflow.operators.python_operator import PythonOperator
from airflow.exceptions import AirflowException
from airflow.operators.sensors import ExternalTaskSensor


def run_sql(hook, sql):
    logging.info('Executing: ' + sql)
    hook.run(sql)


def create_tables(**context):
    hook = SqliteHook.get_connection(context['params']['conn_id']).get_hook()
    run_sql(hook, "CREATE TABLE IF NOT EXISTS data (time TIMESTAMP, value INT);")
    run_sql(hook, "CREATE TABLE IF NOT EXISTS hourly (hour TIMESTAMP, total INT);")


def store_recording(**context):
    """Stores a random integer from 1 to 10 with timestamp into data table"""

    conn = SqliteHook.get_connection(context['params']['conn_id']).get_hook().get_conn()
    time = context['execution_date']

    values = (time, random.randint(1, 10))
    logging.info('Inserting: {0:%Y-%m-%d %H:%M:%S}, {1}'.format(*values))

    with conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO data VALUES (?, ?)", values)


def calc_hourly_totals(**context):
    """Calculates sum of values from data table for the previous hour and puts it into totals table"""

    conn = SqliteHook.get_connection(context['params']['conn_id']).get_hook().get_conn()
    hour = context['execution_date']
    prev_hour = hour - timedelta(hours=1)

    with conn:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM data "
                    "WHERE strftime('%Y-%m-%d %H', time) = strftime('%Y-%m-%d %H', ?)", (prev_hour,))

        data_count = cur.fetchone()[0]
        logging.info('Found {} values for {}'.format(data_count, hour))

        if data_count != 4:
            logging.warn('Need all 4 values to calculate hourly value.')
            raise AirflowException("Need all 4 values to calculate hourly value.")

        cur.execute("SELECT count(*) FROM hourly "
                    "WHERE hour = strftime('%Y-%m-%d %H:00:00', ?)", (hour,))

        hour_count = cur.fetchone()[0]
        if hour_count:
            logging.warn('There is an hourly value for {} already.'.format(hour))
            return

        cur.execute("INSERT INTO hourly SELECT strftime('%Y-%m-%d %H:00:00', ?), sum(value) FROM data "
                    "WHERE strftime('%Y-%m-%d %H', time) = strftime('%Y-%m-%d %H', ?)", (hour, prev_hour))
        logging.info('Inserted hourly value for {}.'.format(hour))


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2016, 11, 26),
    'retries': 5,
    'retry_delay': timedelta(minutes=1),
    'dagrun_timeout': timedelta(minutes=1),
    'params': {
        'conn_id': 'sqlite_default',
    }
}

with DAG('simple_etl_create_tables', default_args=default_args.copy(),
         schedule_interval='@once') as dag:
    (
        dag
        >> PythonOperator(
            task_id='create_table',
            priority_weight=100,
            provide_context=True,
            python_callable=create_tables)
    )

with DAG('simple_etl_store_recording', default_args=default_args.copy(),
         schedule_interval='0/15 * * * *') as dag2:
    (
        dag2
        >> PythonOperator(
            task_id='store_recording',
            priority_weight=10,
            provide_context=True,
            python_callable=store_recording)
    )

with DAG('simple_etl_calc_hourly_totals', default_args=default_args.copy(),
         start_date=default_args['start_date'] + timedelta(hours=1),
         schedule_interval='0 * * * *') as dag3:
    (
        dag3
        >> ExternalTaskSensor(
            task_id='wait_for_data',
            external_dag_id='simple_etl_store_recording',
            external_task_id='store_recording',
            retry_delay=timedelta(minutes=15),
            timeout=60)
        >> PythonOperator(
            task_id='calc_hourly_totals',
            provide_context=True,
            python_callable=calc_hourly_totals)
    )
