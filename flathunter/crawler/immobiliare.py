"""Expose crawler for Immobiliare"""
import re

from flathunter.logging import logger
from flathunter.abstract_crawler import Crawler


class Immobiliare(Crawler):
    """Implementation of Crawler interface for Immobiliare"""

    URL_PATTERN = re.compile(r'https://www\.immobiliare\.it')

    def __init__(self, config):
        super().__init__(config)
        self.config = config

    # pylint: disable=too-many-locals
    def extract_data(self, raw_data):
        """Extracts all exposes from a provided Soup object"""
        entries = []

        results = raw_data.find(
            'ul', {"data-cy": "search-layout-list"})

        items = results.select("div.in-listingCard")

        for row in items:
            title_row = row.find('a', {"class": "in-listingCardTitle"})
            title = title_row.text.strip()
            url = title_row['href']
            flat_id = title_row['href'].split("/")[-2:][0]

            image_item = row.find_all('img')
            image = image_item[0]['src'] if image_item else ""

            # the items arrange like so:
            # 0: number of rooms
            # 1: size of the apartment
            details_list = row.find_all(
                "div", {"class": "in-listingCardFeatureList__item"})

            price_li = row.find(
                "div", {"class": "in-listingCardPrice"})

            price_re = re.match(
                r".*\s([0-9]+.*)$",
                # if there is a discount on the price, then there will be a <div>,
                # otherwise the text we are looking for is directly inside the <li>
                (price_li.find("div") if price_li.find(
                    "div") else price_li).text.strip()
            )
            price = "???"
            if price_re is not None:
                price = price_re[1]

            detail_texts = [ item.find("span").text.strip() for item in details_list ]
            room_counts = [ match.group(1) for text in detail_texts
                if (match := re.match(r"(\d+)\+? local[ie]", text)) is not None ]
            if len(room_counts) > 0:
                rooms = room_counts[0]
            else:
                rooms = None
            sizes = [ match.group(1) for text in detail_texts
                if (match := re.match(r"(\d+) m²", text)) is not None ]
            if len(sizes) > 0:
                size = sizes[0]
            else:
                size = None

            address_match = re.match(r"\w+\s(.*)$", title)
            address = address_match[1] if address_match else ""

            details = {
                'id': int(flat_id),
                'image': image,
                'url': url,
                'title': title,
                'price': price,
                'size': size,
                'rooms': rooms,
                'address': address,
                'crawler': self.get_name()
            }

            entries.append(details)

        logger.debug('Number of entries found: %d', len(entries))

        return entries
