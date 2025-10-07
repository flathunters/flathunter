"""Expose crawler for ImmoWelt"""
import re
import datetime
import hashlib

from bs4 import BeautifulSoup, Tag

from flathunter.logging import logger
from flathunter.abstract_crawler import Crawler

class Immowelt(Crawler):
    """Implementation of Crawler interface for ImmoWelt"""

    URL_PATTERN = re.compile(r'https://www\.immowelt\.de')

    def __init__(self, config):
        super().__init__(config)
        self.config = config

    def get_expose_details(self, expose):
        """Loads additional details for an expose by processing the expose detail URL"""
        soup = self.get_page(expose['url'])
        date = datetime.datetime.now().strftime("%2d.%2m.%Y")
        expose['from'] = date

        immo_div = soup.find("app-estate-object-informations")
        if not isinstance(immo_div, Tag):
            return expose
        immo_div = soup.find("div", {"class": "equipment ng-star-inserted"})
        if not isinstance(immo_div, Tag):
            return expose

        details = immo_div.find_all("p")
        for detail in details:
            if detail.text.strip() == "Bezug":
                date = detail.findNext("p").text.strip()
                no_exact_date_given = re.match(
                    r'.*sofort.*|.*Nach Vereinbarung.*',
                    date,
                    re.MULTILINE|re.DOTALL|re.IGNORECASE
                )
                if no_exact_date_given:
                    date = datetime.datetime.now().strftime("%2d.%2m.%Y")
                break
        expose['from'] = date
        return expose

    # pylint: disable=too-many-locals
    def extract_data(self, raw_data: BeautifulSoup):
        """Extracts all exposes from a provided Soup object"""
        entries = []
        soup_res = raw_data
        if not isinstance(soup_res, Tag):
            return []

        advertisements = soup_res.find_all("div", attrs={"class": "css-79elbk"})
        for adv in advertisements:
            try:
                title = adv.find("div", {"class": "css-1cbj9xw"}).text
            except AttributeError:
                title = ""

            try:
                price = adv.find(
                    "div", attrs={"data-testid": "cardmfe-price-testid"}).text
            except AttributeError:
                price = ""

            try:
                descriptions = adv.find("div",
                    attrs={"data-testid": "cardmfe-keyfacts-testid"}).children
                descriptions = [result.text for result in descriptions]
            except AttributeError:
                descriptions = []

            size = list(filter(lambda x: "m²" in x, descriptions))
            try:
                size = size[0]
            except IndexError:
                size = ""

            rooms = list(filter(lambda x: "Zimmer" in x, descriptions))
            try:
                rooms = rooms[0]
            except IndexError:
                rooms = ""

            id_element = adv.find("a")
            try:
                url = id_element.get("href")
                if "https" not in url:
                    url = "https://immowelt.de/" + url
            except (AttributeError, TypeError):
                continue

            picture = adv.find("img")
            image = None
            if picture:
                image = picture.get('src')

            try:
                address = adv.find(
                    "div", attrs={"data-testid": "cardmfe-description-box-address"}
                  ).text
            except AttributeError:
                address = ""
            ad_id = url.split('/')[-1]
            processed_id = int(
              hashlib.sha256(ad_id.encode('utf-8')).hexdigest(), 16
            ) % 10**16

            details = {
                'id': processed_id,
                'image': image,
                'url': url,
                'title': title.strip(),
                'rooms': rooms,
                'price': price,
                'size': size,
                'address': address,
                'crawler': self.get_name()
            }
            entries.append(details)

        logger.debug('Number of entries found: %d', len(entries))
        return entries
