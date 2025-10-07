"""Expose crawler for Kleinanzeigen"""
import re
import datetime

from bs4 import Tag

from flathunter.webdriver_crawler import WebdriverCrawler
from flathunter.logging import logger

class Kleinanzeigen(WebdriverCrawler):
    """Implementation of Crawler interface for Kleinanzeigen"""

    URL_PATTERN = re.compile(r'https://www\.kleinanzeigen\.de')
    MONTHS = {
        "Januar": "01",
        "Februar": "02",
        "März": "03",
        "April": "04",
        "Mai": "05",
        "Juni": "06",
        "Juli": "07",
        "August": "08",
        "September": "09",
        "Oktober": "10",
        "November": "11",
        "Dezember": "12"
    }

    def get_expose_details(self, expose):
        soup = self.get_page(expose['url'], self.get_driver())
        for detail in soup.find_all('li', {"class": "addetailslist--detail"}):
            if re.match(r'Verfügbar ab', detail.text):
                date_string = re.match(r'(\w+) (\d{4})', detail.text)
                if date_string is not None:
                    expose['from'] = "01." + self.MONTHS[date_string[1]] + "." + date_string[2]
        if 'from' not in expose:
            expose['from'] = datetime.datetime.now().strftime('%02d.%02m.%Y')
        return expose

    # pylint: disable=too-many-locals
    def extract_data(self, raw_data):
        """Extracts all exposes from a provided Soup object"""
        entries = []
        soup = raw_data.find(id="srchrslt-adtable")

        exposes = soup.find_all("article", class_="aditem")
        for  expose in exposes:

            title_elem = expose.find(class_="ellipsis")
            if title_elem.get("href"):
                url = title_elem.get("href")
            else:
                # If there is no title element, just continue since we can't provide an URL
                continue

            try:
                price = expose.find(
                    class_="aditem-main--middle--price-shipping--price").text.strip()
                tags = expose.find_all(class_="simpletag")
                address = expose.find("div", {"class": "aditem-main--top--left"})
                image_element = expose.find("div", {"class": "galleryimage-element"})
            except AttributeError as error:
                logger.warning("Unable to process eBay expose: %s", str(error))
                continue

            if image_element is not None:
                image = image_element["data-imgsrc"]
            else:
                image = None

            address = address.text.strip()
            address = address.replace('\n', ' ').replace('\r', '')
            address = " ".join(address.split())

            rooms = ""
            if len(tags) > 1:
                rooms_match = re.search(r'\d+[.|,]*\d*', tags[1].text, flags=re.MULTILINE)
                if rooms_match is not None:
                    rooms = rooms_match.group()

            try:
                size = tags[0].text.strip()
            except (IndexError, TypeError):
                size = ""

            details = {
                'id': int(expose.get("data-adid")),
                'image': image,
                'url': ("https://www.kleinanzeigen.de" + url),
                'title': title_elem.text.strip(),
                'price': price,
                'size': size,
                'rooms': rooms,
                'address': address,
                'crawler': self.get_name()
            }
            entries.append(details)

        logger.debug('Number of entries found: %d', len(entries))

        return entries

    def load_address(self, url):
        """Extract address from expose itself"""
        expose_soup = self.get_page(url)
        street_raw = ""
        street_el = expose_soup.find(id="street-address")
        if isinstance(street_el, Tag):
            street_raw = street_el.text
        address_raw = ""
        address_el = expose_soup.find(id="viewad-locality")
        if isinstance(address_el, Tag):
            address_raw = address_el.text

        return address_raw.strip().replace("\n", "") + " " + street_raw.strip()
