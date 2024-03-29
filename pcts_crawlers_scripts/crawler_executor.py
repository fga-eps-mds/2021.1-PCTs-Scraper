import os
import gc
import sys
import time

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from scrapy.utils.log import configure_logging

from twisted.internet import reactor
from multiprocessing.context import Process

from pcts_crawlers.spiders.generic_crawler import GenericCrawlerSpider

keywords = [
    "povos e comunidades tradicionais",
    "quilombolas",
]


def run_generic_crawler(crawler_args, keyword, settings_file_path="pcts_crawlers.settings"):
    configure_logging({'LOG_FORMAT': '%(levelname)s: %(message)s'})
    print("=======================================================================")
    print(f"INICIAR CRAWLER {crawler_args['site_name']}. KEYWORD: {keyword}")
    os.environ.setdefault('SCRAPY_SETTINGS_MODULE', settings_file_path)
    projects_settings = get_project_settings()

    # Crawler run
    crawler = CrawlerProcess(projects_settings)
    crawler_instance = crawler.create_crawler(GenericCrawlerSpider)

    crawler.crawl(
        crawler_instance,
        **crawler_args,
        keyword=keyword
    )

    crawler.start()

    stats = crawler_instance.stats.get_stats()
    stats["keyword"] = keyword

    print("========================= METRICAS =========================")
    print("METRICAS:")
    print(stats)
    print("========================= METRICAS =========================")

    return stats


if __name__ == '__main__':
    try:
        crawler_args = {
            "site_name": "stj",
            "site_name_display": "STJ",
            "task_name": "stj_crawler",
            "url_root": "https://www.stj.jus.br/sites/portalp/Paginas/inc/ResultadoDaBusca.aspx",
            "qs_search_keyword_param": "q",
            "allowed_domains": [
                "www.stj.jus.br"
            ],
            "allowed_paths": [
                "sites/portalp/Paginas/Comunicacao/Noticias"
            ],
            "page_load_timeout": 5,
            "cron_minute": "0",
            "cron_hour": "10",
            "cron_day_of_week": "*",
            "cron_day_of_month": "*",
            "cron_month_of_year": "*",
            "created_at": "2021-10-17T19:26:54.660443"
        }

        run_generic_crawler(crawler_args, keyword="quilombolas")
    finally:
        gc.collect()
