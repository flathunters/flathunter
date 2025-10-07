"""Expose crawler for ImmobilienScout"""
import re


from flathunter.abstract_crawler import Crawler
from flathunter.logging import logger

STATIC_URL_PATTERN = re.compile(r'https://www\.immobilienscout24\.de')

class Immobilienscout(Crawler):
    """Implementation of Crawler interface for ImmobilienScout"""

    URL_PATTERN = STATIC_URL_PATTERN


    RESULT_LIMIT = 50

    FALLBACK_IMAGE_URL = "https://www.static-immobilienscout24.de/statpic/placeholder_house/" + \
                         "496c95154de31a357afa978cdb7f15f0_placeholder_medium.png"





    def get_results(self, search_url, max_pages=None):
        """Loads the exposes from the ImmoScout site, starting at the provided URL"""
        # convert to paged URL
        # if '/P-' in search_url:
        #     search_url = re.sub(r"/Suche/(.+?)/P-\d+", "/Suche/\1/P-{0}", search_url)
        # else:
        #     search_url = re.sub(r"/Suche/(.+?)/", r"/Suche/\1/P-{0}/", search_url)
        if '&pagenumber' in search_url:
            search_url = re.sub(r"&pagenumber=[0-9]", "&pagenumber={0}", search_url)
        else:
            search_url = search_url + '&pagenumber={0}'
        logger.debug("Got search URL %s", search_url)

        # load first page to get number of entries
        page_no = 1
        soup = self.get_page(search_url, self.get_driver(), page_no)

        # If we are using Selenium, just parse the results from the JSON in the page response
        if self.get_driver() is not None:
            return self.get_entries_from_javascript()

        no_of_results = get_result_count(soup)

        # get data from first page
        entries = self.extract_data(soup)

        # iterate over all remaining pages
        while len(entries) < min(no_of_results, self.RESULT_LIMIT) and \
                (max_pages is None or page_no < max_pages):
            logger.debug(
                '(Next page) Number of entries: %d / Number of results: %d',
                len(entries), no_of_results)
            page_no += 1
            soup = self.get_page(search_url, self.get_driver(), page_no)
            cur_entry = self.extract_data(soup)
            if isinstance(cur_entry, list):
                break
            entries.extend(cur_entry)
        return entries

        return entries
