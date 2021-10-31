import sys
import os
import json
from datetime import datetime
from celery import Celery
from celery.app import task as task_obj
from crawlers.models import CrawlerExecutionGroup
from crawlers.models import Crawler
from celery.canvas import group, chain, chord
from celery.schedules import crontab
from celery import shared_task, task
from django_celery_beat.models import PeriodicTask, CrontabSchedule

from pcts_crawlers_api.celery import app as celery_app

from crawlers.models import STARTED
from crawlers.models import SUCCESS
from crawlers.models import FAILURE
from crawlers.models import CrawlerExecution

from keywords.models import Keyword

ENVIRONMENT_EXEC = os.environ.get("PROJECT_ENV_EXECUTOR", default="HOST")
if ENVIRONMENT_EXEC == "DOCKER":
    sys.path.append('/app/pcts_crawlers_scripts')
elif ENVIRONMENT_EXEC == "TEST":
    sys.path.append('pcts_crawlers_scripts')
else:
    sys.path.append('../pcts_crawlers_scripts')
from crawler_executor import run_generic_crawler


def task_crawler_finish_wrapper(task_name_prefix):
    @task(name=f"{task_name_prefix}_finish", bind=True)
    def task_finish_group_execution(self, subtasks_result, crawler_execution_group_id):
        crawler_execution_group = CrawlerExecutionGroup.objects.get(
            pk=crawler_execution_group_id
        )

        crawler_execution_group.state = \
            SUCCESS if subtasks_result else FAILURE
        crawler_execution_group.finish_datetime = datetime.now()
        crawler_execution_group.save()

        return subtasks_result

    return task_finish_group_execution


def task_crawler_keyword_wrapper(task_name_prefix):
    @task(name=f"{task_name_prefix}_keyword", bind=True, time_limit=sys.maxsize)
    def task_crawler_subtask(self, prev_subtasks,
                             crawler_execution_group_id, crawler_args,
                             keyword, **kwargs):
        crawler_execution_group = CrawlerExecutionGroup.objects.get(
            pk=crawler_execution_group_id
        )

        task_id = self.request.id
        task_instance = celery_app.AsyncResult(task_id)
        result_meta = task_instance._get_task_meta()
        task_name = result_meta.get("task_name")

        print("ATRIBUTOS TASK EXEC")
        print("TASK_EXEC_ID:", self.request.id)
        print("TASK_EXEC_INSTANCE_NAME:", task_name)

        # Start execution monitoring
        crawler_execution = CrawlerExecution.objects.create(
            crawler_execution_group=crawler_execution_group,
            task_id=task_id,
            task_name=task_name,
            keyword=keyword,
            state=STARTED
        )

        result_state = True

        try:
            execution_stats = run_generic_crawler(
                crawler_args=crawler_args,
                keyword=keyword
            )

            # Update execution monitoring on success
            crawler_execution.crawled_pages = execution_stats.get(
                "downloader/request_count") or 0
            crawler_execution.saved_records = execution_stats.get(
                "saved_records") or 0
            crawler_execution.dropped_records = execution_stats.get(
                "droped_records") or 0
            crawler_execution.state = SUCCESS
        except Exception as e:
            result_state = False
            crawler_execution.state = FAILURE
            crawler_execution.error_log = str(e)
        finally:
            crawler_execution.finish_datetime = datetime.now()
            crawler_execution.save()

        if prev_subtasks == None:
            return result_state
        else:
            return prev_subtasks and result_state

    return task_crawler_subtask


def task_crawler_group_wrapper(task_name):
    """ Wrapper do task group de execucao de um crawler inteiro
        e a subtask de execucao de uma keyword por vez
    """
    @task(name=f"{task_name}_start", bind=True)
    def task_crawler_group(self, task_name_prefix, crawler_id, crawler_args,
                           keywords=[], **kwargs):
        crawler = Crawler.objects.get(pk=crawler_id)

        task_id = self.request.id
        task_instance = celery_app.AsyncResult(task_id)
        result_meta = task_instance._get_task_meta()
        task_name = result_meta.get("task_name")

        print("ATRIBUTOS TASK EXEC GROUP")
        print("TASK_EXEC_GROUP_ID:", self.request.id)
        print("TASK_EXEC_GROUP_INSTANCE_NAME:", task_name)

        crawler_group = CrawlerExecutionGroup.objects.create(
            crawler=crawler,
            task_name=task_name,
            state=STARTED,
        )

        task_crawler_subtasks = []
        if not keywords:
            keywords.append("")

        for idx, keyword in enumerate(keywords):
            task_args = {
                "crawler_execution_group_id": crawler_group.id,
                "crawler_args": crawler_args,
                "keyword": keyword,
            }

            # A primeira task da chain, possui o argumento a prev_subtasks.
            # Nas próximas tasks, o próprio Celery irá setar
            # este atributo com o resultado da task anterior
            if idx == 0:
                task_args["prev_subtasks"] = None

            task_crawler_subtasks.append(
                task_crawler_keyword_wrapper(task_name_prefix).subtask(
                    kwargs=task_args
                )
            )

        task_finish_group_exec_subtask = \
            task_crawler_finish_wrapper(task_name_prefix).subtask(
                kwargs={
                    "crawler_execution_group_id": crawler_group.id,
                },
            )

        chain(
            *task_crawler_subtasks,
            task_finish_group_exec_subtask
        ).apply_async()

        return True

    return task_crawler_group


def get_periodic_task(task_name):
    try:
        return PeriodicTask.objects.get(name=task_name)
    except Exception:
        return None


def create_periodic_task(sender: Celery, taskname, crontab_args,
                         task_kwargs):

    task_kwargs["task_name_prefix"] = taskname
    sender.add_periodic_task(
        schedule=crontab(
            **crontab_args
        ),
        sig=task_crawler_group_wrapper(
            taskname
        ).subtask(kwargs=task_kwargs),
        name=taskname,
    )


def get_crontab_scheduler(crontab_args):
    try:
        crontab_scheduler = CrontabSchedule.objects.get(**crontab_args)
    except Exception:
        crontab_scheduler = CrontabSchedule.objects.create(**crontab_args)
    return crontab_scheduler


def update_periodic_task(task: PeriodicTask, crontab_args, task_kwargs):
    task.kwargs = json.dumps(task_kwargs)
    task.crontab = get_crontab_scheduler(crontab_args)
    task.interval = None
    task.solar = None
    task.clocked = None
    task.save()


def create_or_update_periodic_task(sender: Celery, crawler: Crawler,
                                   keywords=[]):
    task_kwargs = {
        "crawler_id": crawler.id,
        "crawler_args": {
            "site_name": crawler.site_name,
            "url_root": crawler.url_root,
            "qs_search_keyword_param": crawler.qs_search_keyword_param,
            "contains_end_path_keyword": crawler.contains_end_path_keyword,
            "task_name_prefix": crawler.task_name_prefix,
            "allowed_domains": crawler.allowed_domains,
            "allowed_paths": crawler.allowed_paths,
            "retries": crawler.retries,
            "page_load_timeout": crawler.page_load_timeout,
            "contains_dynamic_js_load": crawler.contains_dynamic_js_load,
        },
        "keywords": keywords,
    }
    crontab_args = {
        "minute": crawler.cron_minute,
        "hour": crawler.cron_hour,
        "day_of_week": crawler.cron_day_of_week,
        "day_of_month": crawler.cron_day_of_month,
        "month_of_year": crawler.cron_month_of_year
    }

    taskname = crawler.task_name_prefix
    task = get_periodic_task(taskname)
    if task:
        print("ATUALIZANDO TASK:", taskname)
        update_periodic_task(
            task,
            crontab_args,
            task_kwargs,
        )
    else:
        print("ADICIONANDO TASK:", taskname)
        create_periodic_task(
            sender,
            taskname,
            crontab_args,
            task_kwargs,
        )


# ============================= AUTO CREATE SCHEDULERS ON STARTUP
@celery_app.on_after_finalize.connect
def sync_periodic_crawlers(sender: Celery, **kwargs):
    """ Adiciona jobs agendados a partir dos crawler default disponiveis
    """

    try:
        keywords = [
            keyword.keyword
            for keyword in Keyword.objects.all()
        ]
    except Exception:
        keywords = []

    print("SINCRONIZANDO PERIODIC TASKS")
    crawlers = Crawler.objects.all()
    for crawler in crawlers:
        print("SINCRONIZAR TASK:", crawler.task_name_prefix)
        try:
            create_or_update_periodic_task(sender, crawler, keywords)
        except Exception as e:
            print("EXCECAO AO SINCRONIZAR TASK:", str(e))
            raise e
