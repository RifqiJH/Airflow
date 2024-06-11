from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.hooks.postgres_hook import PostgresHook
from airflow.utils.dates import days_ago
import logging
import pendulum  # Tambahkan import pendulum di sini
from airflow.hooks.mssql_hook import MsSqlHook

# Default arguments
default_args = {
    'owner': 'airflow',
    'start_date': days_ago(1),
}

# Instantiate the DAG
dag = DAG(
    'dag_ingest_cybertrack_nmb_v_merchant_transaction',
    default_args=default_args,
    schedule_interval='@daily',
    catchup=False,
    start_date=pendulum.datetime(2024, 1, 1, tz="Asia/Jakarta")  # Tambahkan zona waktu di sini
)

def extract_from_mssql(**kwargs):
    mssql_hook = MsSqlHook(mssql_conn_id='sql_server_conn')
    sql = "SELECT * FROM raw_data.cybertrack_nmb_v_merchant_transaction;"
    records = mssql_hook.get_records(sql)
    
    # Menambahkan waktu pengambilan data dengan waktu saat ini di zona waktu Asia/Jakarta
    time_get_data = pendulum.now("Asia/Jakarta").strftime('%Y-%m-%d %H:%M:%S')
    
    # Menambahkan waktu pengambilan data ke setiap record
    records_with_time = [(record + (time_get_data,)) for record in records]
    kwargs['ti'].xcom_push(key='mssql_data', value=records_with_time)

def load_to_postgresql(**kwargs):
    ti = kwargs['ti']
    data = ti.xcom_pull(key='mssql_data', task_ids='extract_from_mssql')
    pg_hook = PostgresHook(postgres_conn_id='postgres_conn')
    
    insert_query = """
    INSERT INTO raw_data.cybertrack_nmb_v_merchant_transaction (
        "Id",
        "MPANID",
        "NMID",
        "MerchantID",
        "MerchantName",
        "MerchantPhone",
        "MerchantEmail",
        "MerchantType",
        "MerchantStatus",
        "MerchantCurrency",
        "RegisterLongitude",
        "RegisterLatitude",
        "RegisterCountry",
        "TransactionID",
        "TransactionTimestamp",
        "TransactionDatetime",
        "TransactionType",
        "TransactionChannel",
        "TransactionAmount",
        "IssuerName",
        "TransactionStatus",
        "TransactionMessage",
        "CPANID",
        "StoreID",
        "IssuerID",
        "MID",
        "timegetdata"  
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""
    
    for record in data:
        pg_hook.run(insert_query, parameters=record)

def print_total_rows(**kwargs):
    ti = kwargs['ti']
    data = ti.xcom_pull(key='mssql_data', task_ids='extract_from_mssql')
    total_rows = len(data)
    logging.info(f"Total rows of data extracted: {total_rows}")

# Tasks
extract_task = PythonOperator(
    task_id='extract_from_mssql',
    python_callable=extract_from_mssql,
    provide_context=True,
    dag=dag,
)

load_task = PythonOperator(
    task_id='load_to_postgresql',
    python_callable=load_to_postgresql,
    provide_context=True,
    dag=dag,
)

print_total_rows_task = PythonOperator(
    task_id='print_total_rows',
    python_callable=print_total_rows,
    provide_context=True,
    dag=dag,
)

# Task dependencies
extract_task >> load_task >> print_total_rows_task
