"""Coleta diária das fontes habilitadas de dengue nos municípios de SP."""
import json
import os
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from airflow.sdk import dag, task


def request_collection(body):
    request = urllib.request.Request("http://backend:8000/api/internal/coleta/", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Coleta-Token": os.environ["COLETA_TOKEN"]}, method="POST")
    with urllib.request.urlopen(request, timeout=115) as response:
        return json.load(response)


@dag(dag_id="sme_infodengue_piloto", schedule="0 6 * * *",
     start_date=datetime(2026, 10, 3, tzinfo=ZoneInfo("America/Sao_Paulo")),
     catchup=False, max_active_runs=1, is_paused_upon_creation=False,
     default_args={"retries": 0}, tags=["sme", "infodengue"])
def infodengue_pilot():
    @task(execution_timeout=timedelta(minutes=3))
    def sources():
        return request_collection({"action": "list"})["fontes"]

    @task(execution_timeout=timedelta(minutes=3), do_xcom_push=False, max_active_tis_per_dag=2)
    def collect(source_id):
        result = request_collection({"fonte_id": source_id})
        for run in result["execucoes"]:
            print(run["id"], run["status"], run["quantidade_registros"])

    collect.expand(source_id=sources())


infodengue_pilot()
