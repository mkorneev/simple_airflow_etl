# README #

This is a simple Airflow ETL.

### The task ###

Please create a workflow using any database (e.g. sqlite for simplicity) and ETL framework (preferably airflow) that incorporates the following:

* every 15 minutes inserts a new row into a table including the timestamp and a randomised value between 1 and 10
* at the end of every hour sums up the respective values and stores it in a separate table (with timestamp)

Keep in mind that tasks might be failing and / or might be processed out of order. The ETL should be resilient to these cases.

### How do I get set up? ###

```bash
ansible-playbook roles/airflow.yml
ansible-playbook roles/start-etl.yml
```

### How to check the result? ###

##### Hourly results table
<http://HOST:8080/admin/queryview/?conn_id=sqlite_default&sql=SELECT+*+FROM+hourly+ORDER+BY+hour+DESC>

##### Raw data table
<http://HOST:8080/admin/queryview/?conn_id=sqlite_default&sql=SELECT+*+FROM+data+ORDER+BY+time+DESC>

### Who do I talk to? ###

* Author: Maxim Korneev (maxeem@gmail.com)