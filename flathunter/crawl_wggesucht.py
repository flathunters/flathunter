"""Expose crawler for WgGesucht"""
import logging
import re

import requests
from bs4 import BeautifulSoup
from flathunter.abstract_crawler import Crawler

class CrawlWgGesucht(Crawler):
    """Implementation of Crawler interface for WgGesucht"""

    __log__ = logging.getLogger(__name__)
    URL_PATTERN = re.compile(r'https://www\.wg-gesucht\.de')

    def __init__(self):
        logging.getLogger("requests").setLevel(logging.WARNING)

    # pylint: disable=too-many-locals
    def extract_data(self, soup):
        """Extracts all exposes from a provided Soup object"""
        entries = list()

        findings = soup.find_all(lambda e: e.has_attr('id') and e['id'].startswith('liste-'))
        existing_findings = list(
            [e for e in findings if e.has_attr('class') and not 'display-none' in e['class']])

        base_url = 'https://www.wg-gesucht.de/'
        for row in existing_findings:
            title_row = row.find('h3', {"class": "truncate_title"})
            title = title_row.text.strip()
            url = base_url + title_row.find('a')['href']
            image = re.match(r'background-image: url\((.*)\);',
                             row.find('div', {"class": "card_image"}).find('a')['style'])[1]
            detail_string = row.find("div", {"class": "col-xs-11"}).text.strip().split("|")
            details_array = list(map(lambda s: re.sub(' +', ' ',
                                                      re.sub(r'\W', ' ', s.strip())),
                                     detail_string))
            numbers_row = row.find("div", {"class": "middle"})
            price = numbers_row.find("div", {"class": "col-xs-3"}).text.strip()
            rooms = re.findall(r'\d Zimmer', details_array[0])[0][:1]
            dates = re.findall(r'\d{2}.\d{2}.\d{4}',
                               numbers_row.find("div", {"class": "text-center"}).text)
            size = re.findall(r'\d{1,4}\sm²',
                              numbers_row.find("div", {"class": "text-right"}).text)[0]

            details = {
                'id': int(url.split('.')[-2]),
                'image': image,
                'url': url,
                'title': "%s ab dem %s" % (title, dates[0]),
                'price': price,
                'size': size,
                'rooms': rooms,
                'address': url,
                'crawler': self.get_name()
            }
            if len(dates) == 2:
                details['from'] = dates[0]
                details['to'] = dates[1]
            elif len(dates) == 1:
                details['from'] = dates[0]

            entries.append(details)

        self.__log__.debug('extracted: %d', entries)

        return entries

    @staticmethod
    def load_address(url):
        """Extract address from expose itself"""
        response = requests.get(url)
        flat = BeautifulSoup(response.content, 'lxml')
        address = ' '.join(flat.find('div', {"class": "col-sm-4 mb10"})\
                     .find("a", {"href": "#"}).text.strip().split())
        return address
