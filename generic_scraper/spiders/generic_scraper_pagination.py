from time import sleep
import os
import json
from datetime import datetime
import re
import unicodedata

from scrapy.spiders import CrawlSpider, Rule, Spider
from scrapy import Request
from scrapy.linkextractors import LinkExtractor
from scrapy.http.response.html import HtmlResponse
from scrapy_selenium import SeleniumRequest
from scrapy.selector.unified import Selector

from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from scrapy_splash import SplashRequest

DEFAULT_ROOT_OUTPUT_DATA_FOLDER = f"{os.getcwd()}/output_data/"


class ScraperPagination(Spider):
    """ Generic Scraper for use on paginated item listing page of the target website
    """

    name = 'generic-scraper-pagination'
    root_output_data_folder = DEFAULT_ROOT_OUTPUT_DATA_FOLDER
    scraper_start_datetime = datetime.now().strftime("%Y%m%d_%H%M")
    start_urls = []

    def __init__(self, root=None, site_name=None, next_button_xpath=None,
                 called_by_python_script=False, *args, **kwargs):
        """ Initializes ScraperPagination

        Args:
            root(str): root page url
            next_button_xpath(str): XPATH of "Next" button of the listing page
            called_by_python_script(bool): Sinalize if the spider was called by a python script
                True - The extra named arguments can be normal types (string, integer, list)
                False - The extra named arguments can be only strings.
                    In this case is called self.format_shell_options() to format some string
                    arguments to list
            *args: Extra arguments
            **kwargs: Extra named arguments
        """
        self.logger.info("[Scraper Pagination] Source: %s Kwargs: %s",
                         root, kwargs)
        self.source = root
        self.site_name = site_name
        self.output_folder_path = os.path.join(
            self.root_output_data_folder,
            self.site_name,
            self.scraper_start_datetime,
        )
        self.options = kwargs
        self.next_button_xpath = next_button_xpath

        if not called_by_python_script:
            self.format_shell_options()

        ScraperPagination.start_urls.append(root)
        ScraperPagination.allowed_domains = self.options.get('allow_domains')
        self.link_pages_extractor = LinkExtractor(
            allow=self.options.get('allow'),
            deny=self.options.get('deny'),
            allow_domains=self.options.get('allow_domains'),
            deny_domains=self.options.get('deny_domains'),
            restrict_xpaths=self.options.get('items_xpath'),
            canonicalize=False,
            unique=True,
            process_value=None,
            deny_extensions=None,
            restrict_css=self.options.get('restrict_css'),
            strip=True,
        )

        self.create_directory_structure()
        super(ScraperPagination, self).__init__(*args, **kwargs)

    def start_requests(self, *args, **kwargs):
        yield SeleniumRequest(
            url=self.source,
            callback=self.parse_home_pagination,
        )

    def parse_home_pagination(self, response: HtmlResponse):
        driver: WebDriver = response.request.meta['driver']

        found_urls = []
        old_found_urls = []

        while True:
            try:
                # Get links and call inner pages
                old_found_urls = found_urls
                found_urls = self.get_page_links(response)

                # Pagination stop condition
                if found_urls == old_found_urls:
                    raise Exception("End of Pagination")

                if len(found_urls) > 0:
                    for url in found_urls:
                        yield dict(
                            link=url,
                            meta=dict(source=self.source)
                        )
                        yield SplashRequest(
                            url=url,
                            callback=self.parse_article_page,
                            endpoint='render.html',
                            args={'wait': 1},
                        )

                        sleep(0.1)

                # Follow next Pagination
                next_button = driver.find_element_by_xpath(
                    self.next_button_xpath)
                print("Next Page")
                print(next_button)
                old_url = driver.current_url

                # click the button to go to next page
                driver.execute_script("arguments[0].click();", next_button)
                print(("RESUMO", f"CURRENT URL:{driver.current_url} == {old_url}",
                      f"\n\n\nFOUND_URLS: OLD_URLS >> {old_found_urls} \n==\n NEW_URLS: >> {found_urls}"))
                sleep(2)

            except Exception as e:
                print(str(e))
                break
        driver.close()

    def parse_article_page(self, response: HtmlResponse):
        page_content = dict(url=response.url)
        page_content['content'] = response.body.decode("utf-8")
        page_content['extracted_at'] = int(datetime.now().timestamp())

        page_title = response.xpath("/html/head/title/text()").extract_first()
        print("Pagina Carregada:", page_content)

        self.save_page_content(page_title, page_content)

    def get_page_links(self, response):
        links = self.link_pages_extractor.extract_links(response)
        str_links = []
        for link in links:
            str_links.append(link.url)
        return str_links

    def format_shell_options(self):
        allowed_options = [
            'allow',
            'deny',
            'allow_domains',
            'deny_domains',
            'restrict_xpaths',
            'restrict_css',
            'items_xpath',
        ]
        for key in allowed_options:
            if self.options.get(key, None) is None:
                self.options[key] = []
            else:
                self.options[key] = self.options.get(key).split(',')

    def create_directory_structure(self):
        if not os.path.exists(self.output_folder_path):
            os.makedirs(self.output_folder_path)

    def save_page_content(self, page_title, content):
        current_time = datetime.now().strftime("%H%M%S_%f")
        page_title = self.clean_text(page_title)
        file_path = os.path.join(
            self.output_folder_path,
            f"{page_title}_{current_time}.json"
        )

        try:
            with open(file_path, "w") as page_content_f:
                page_content_f.write(json.dumps(content))
        except Exception as e:
            self.logger.error(
                "Falha ao Carregar Arquivo de Saida: %s",
                page_title
            )
            self.logger.error("Erro:", str(e))

    def clean_text(self, text):
        normalized_text = unicodedata.normalize('NFKD', text.lower())\
            .encode('ascii', 'ignore')
        return "_".join(re.findall(
            "\w+",
            normalized_text.decode('ascii'))
        )
