import os
import gc

import scrapy
from scrapy.crawler import CrawlerRunner
from scrapy.spiders import Spider
from scrapy.utils.project import get_project_settings
from scrapy.utils.log import configure_logging

from twisted.internet import reactor

from pcts_scrapers.spiders import mpf_scraper
from pcts_scrapers.spiders import incra_scraper

from multiprocessing.context import Process

scrapers = [
    mpf_scraper.MpfScraperSpider,
    incra_scraper.IncraScraperSpider,
]

keywords = [
    "povos e comunidades tradicionais",
    "quilombolas",
]


def run_scrapers(settings_file_path="pcts_scrapers.settings", custom_project_settings={}):
    """ Execute Scrapy ScraperPagination spider
    Args:
        settings_file_path(str):    Filepath of Scrapy project settings.
            Example: "path.to.file.settings"
        custom_project_settings(str):   Customm Attributes settings to update default
        project settings.
            Example: {"SPIDER_MODULES": ['path.to.file.spiders']}
    """

    print("EXECUTAR SCRAPER")
    os.environ.setdefault('SCRAPY_SETTINGS_MODULE', settings_file_path)

    projects_settings = get_project_settings()

    projects_settings.update(custom_project_settings)

    for scraper in scrapers:
        process_scraper_source = Process(
            target=run_scraper_source,
            args=(projects_settings, scraper, keywords)
        )
        process_scraper_source.start()
        process_scraper_source.join()


def run_scraper_source(projects_settings, scraper: Spider, keywords: []):
    for keyword in keywords:
        print(f"=============================================")
        print(f"Scraping {scraper.name} source, Keyword: {keyword}")

        process_scraper_keyword = Process(
            target=run_scraper_keyword,
            args=(projects_settings, scraper, keyword)
        )
        process_scraper_keyword.start()
        process_scraper_keyword.join()

        print(f"Source {scraper.name} scraped")
        print(f"=============================================\n")


def run_scraper_keyword(projects_settings, scraper: Spider, keyword=""):
    configure_logging({'LOG_FORMAT': '%(levelname)s: %(message)s'})
    crawler = CrawlerRunner(projects_settings)

    running_process = crawler.crawl(
        scraper,
        keyword=keyword
    )

    running_process.addBoth(lambda _: reactor.stop())
    reactor.run()


if __name__ == '__main__':
    try:
        run_scrapers()
    finally:
        gc.collect()
