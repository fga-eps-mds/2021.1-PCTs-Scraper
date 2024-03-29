import os
import re
import difflib
from time import sleep

from scrapy.spiders import Spider
from scrapy.linkextractors import LinkExtractor
from scrapy.link import Link
from scrapy.http.response.html import HtmlResponse
from scrapy_selenium import SeleniumRequest
from scrapy.selector.unified import Selector
from scrapy import Request


from selenium.webdriver.chrome.webdriver import WebDriver
from ..items import CrawlerItem

DEFAULT_TITLE_XPATH = "/html/head/title/text()"
DEFAULT_ALL_CONTENT_XPATH = (
    "//body//*//text()[not(ancestor::script) and not(ancestor::noscript) and not(ancestor::style)]"
)
DEFAULT_CONTENT_XPATH = (
    "//body//*//text()[not(ancestor::script) and not(ancestor::noscript) and "
    "not(ancestor::style) and not(ancestor::header) and not(ancestor::footer) and "
    "not(ancestor::nav) and not(ancestor::menu) and not(ancestor::aside) and "
    "not(ancestor::dialog) and not(ancestor::form) and not(ancestor::a) and "
    "not(ancestor::ul) and not(ancestor::li) and not(ancestor::label)]"
)


class GenericCrawlerSpider(Spider):
    """ Generic Crawler for use on paginated item listing page of the target website
    """

    name = 'generic-crawler'
    start_urls = []

    def __init__(self, url_root, site_name, allowed_domains=None, allowed_paths=None,
                 qs_search_keyword_param=None, contains_end_path_keyword=False,
                 page_load_timeout=2, keyword="", *args, **kwargs):
        """ Initializes GenericCrawlerSpider

        Args:
            url_root(str): root page url
            site_name(str): site name
            allowed_domains(list<str>): url domains allowed to be crawled
            allowed_paths(list<str>): url paths allowed to be crawled
            qs_search_keyword_param(str): query string param where the keyword should be imputed
            page_load_timeout(int): time limit to load page
            keyword(str): word or expression used to search the first page or check affinity
            *args: Extra arguments
            **kwargs: Extra named arguments
        """
        self.logger.info("Generic Crawler Source: %s", url_root)
        self.source_url = url_root
        self.site_name = site_name
        self.allowed_domains = allowed_domains
        self.allowed_paths = allowed_paths
        self.qs_search_keyword_param = qs_search_keyword_param
        self.contains_end_path_keyword = contains_end_path_keyword
        self.page_load_timeout = page_load_timeout
        self.keyword = keyword
        self.start_urls.append(self.source_url)
        self.search_page = True

        self.link_pages_extractor = LinkExtractor(
            allow_domains=self.allowed_domains,
            allow=self.allowed_paths,
            canonicalize=True,
            unique=True,
            process_value=self.normalize_url,
            deny_extensions=None,
            strip=True,
        )

    def normalize_url(self, url):
        # return url.split("#")[0].strip(" /")
        # re.fullmatch("(\w+://)?(\w+\.)+\w+(/(\w+|\#))*/\w+", "teste4.com/#/teste/a#oi")
        # Remove #section da url
        # re.split("(\w)#(?=\w)", url)

        return url.strip(" /")

    def start_requests(self, *args, **kwargs):
        self.define_stats_attributes()

        end_path = ""
        query_string = ""
        if self.contains_end_path_keyword:
            end_path = "/" + str(self.keyword)
        if self.qs_search_keyword_param:
            query_string = f"?{str(self.qs_search_keyword_param)}={str(self.keyword)}"
        entrypoint_url = self.source_url + end_path + query_string

        self.logger.info(f"INITIAL URL: {entrypoint_url}")

        yield self.make_request(
            entrypoint_url,
            'INITIAL_SEARCH_PAGE',
            self.parse_first_page
        )

    def parse_first_page(self, response: HtmlResponse, title):
        driver: WebDriver = response.request.meta['driver']
        sleep(2)
        response = self.create_current_page_response(driver)
        links_found = self.get_page_links(response)

        for link in links_found:
            yield self.make_request(link['url'], link['text'], self.parse_page)

    def parse_page(self, response: HtmlResponse, title, is_test: bool = False):
        driver: WebDriver = response.request.meta['driver']
        sleep(2)
        response = self.create_current_page_response(driver)

        # Extracao de todo o conteudo da pagina
        # Para buscar afinidade com o conteudo na pagina
        # ou a partir dos links
        all_content_list = response.xpath(
            DEFAULT_ALL_CONTENT_XPATH
        ).extract()
        all_content = self.get_alfanumeric_from_text_list(
            all_content_list
        )

        # Follow Links
        if self.check_keyword_affinity(all_content):
            links_found = self.get_page_links(response)
            if not is_test:
                for link in links_found:
                    yield self.make_request(link['url'], link['text'], self.parse_page)
            yield self.data_extraction(response, title)
        else:
            if not is_test:
                self.stats.inc_value('dropped_records_by_keyword_all_content')

    def define_stats_attributes(self):
        self.stats = self.crawler.stats

        self.stats.set_value(
            'dropped_records_by_keyword_all_content',
            0
        )
        self.stats.set_value(
            'dropped_records_by_keyword_restrict_content',
            0
        )

    def make_request(self, url, title, parse_callback):
        return SeleniumRequest(
            url=url,
            callback=parse_callback,
            meta={'donwload_timeout': self.page_load_timeout},
            cb_kwargs={"title": title}
        )

    def data_extraction(self, response: HtmlResponse, title):
        # Extracao restrita a apenas as partes importantes
        # do conteudo da pagina
        restrict_content_list = response.xpath(
            DEFAULT_CONTENT_XPATH
        ).extract()

        restrict_content = self.get_alfanumeric_from_text_list(
            restrict_content_list
        )

        if self.check_keyword_affinity(restrict_content):
            page_content = CrawlerItem()
            page_content['source'] = self.site_name
            page_content['url'] = response.url.strip(" /")
            if title:
                page_content['title'] = title
            else:
                page_content['title'] = response.xpath(
                    DEFAULT_TITLE_XPATH
                ).extract_first()
            page_content['content'] = restrict_content
            return page_content
        else:
            self.stats.inc_value(
                'dropped_records_by_keyword_restrict_content'
            )

    def get_alfanumeric_from_text_list(self, text_list):
        full_text = ' '.join(
            text for text in text_list if text
        ).strip()
        alfanumeric_text_list = re.findall("\w*", full_text)

        return " ".join(
            [text for text in alfanumeric_text_list if text]
        )

    def create_current_page_response(self, driver: WebDriver):
        # Workaround to get always the current
        # response (after js load)
        return HtmlResponse(
            url=driver.current_url,
            body=driver.find_element_by_xpath(
                '//*').get_attribute("outerHTML"),
            encoding='utf-8'
        )

    def check_keyword_affinity(self, content: str):
        return re.search(self.keyword, content, flags=re.IGNORECASE)
        # words = list(map(
        #     lambda word: word.lower(),
        #     content.split(" ")
        # ))
        # matches = difflib.get_close_matches(
        #     self.keyword, words, cutoff=0.9
        # )
        # return len(matches) > 1

    def get_page_links(self, response):
        links = self.link_pages_extractor.extract_links(response)
        str_links = []
        for link in links:
            str_links.append({
                "url": link.url,
                "text": link.text
            })
        return str_links
