"""Expose crawler for WgGesucht"""
import re
from typing import Optional, List, Dict, Any, Union

import requests
from bs4 import BeautifulSoup, Tag

from flathunter.logging import logger
from flathunter.abstract_crawler import Crawler


def get_title(title_row: Tag) -> str:
    """Parse the title from the expose title element"""
    return title_row.text.strip()


def get_url(title_row: Tag) -> Optional[str]:
    """Parse the expose URL from the expose title element"""
    a_element = title_row.find('a')
    if not isinstance(a_element, Tag) \
            or not a_element.has_attr('href') \
            or not isinstance(a_element.attrs['href'], str):
        return None
    return 'https://www.wg-gesucht.de/' + a_element.attrs['href'].removeprefix("/")


def extract_href_style(row: Tag) -> Optional[str]:
    """Extract the style attribute from a image div"""
    div = row.find('div', {"class": "card_image"})
    if not isinstance(div, Tag):
        return None
    a_element = div.find('a')
    if not isinstance(a_element, Tag) or not a_element.has_attr('style'):
        return None
    style = a_element.attrs['style']
    if not isinstance(style, str):
        return None
    return style


def get_image_url(row: Tag) -> Optional[str]:
    """Parse the image url from the expose"""
    href_style = extract_href_style(row)
    if href_style is None:
        return None
    image_match = re.match(r'background-image: url\((.*)\);', href_style)
    if image_match is None:
        return None
    return image_match[1]


def get_rooms(row: Tag) -> str:
    """Parse the number of rooms from the expose"""
    details_el = row.find("div", {"class": "col-xs-11"})
    if not isinstance(details_el, Tag):
        return ""
    detail_string = details_el.text.strip().split("|")
    details_array = list(map(lambda s: re.sub(' +', ' ',
                                              re.sub(r'\W', ' ', s.strip())),
                             detail_string))
    rooms_tmp = re.findall(r'\d Zimmer', details_array[0])
    return rooms_tmp[0][:1] if rooms_tmp else ""


def get_price(numbers_row: Tag) -> Optional[str]:
    """Parse the price from the expose"""
    price_el = numbers_row.find("div", {"class": "col-xs-3"})
    if not isinstance(price_el, Tag):
        return None
    return price_el.text.strip()


def get_dates(numbers_row: Tag) -> List[str]:
    """Parse the advert dates from the expose"""
    date_el = numbers_row.find("div", {"class": "text-center"})
    if not isinstance(date_el, Tag):
        return []
    return re.findall(r'\d{2}.\d{2}.\d{4}', date_el.text)


def get_size(numbers_row: Tag) -> List[str]:
    """Parse the room size from the expose"""
    size_el = numbers_row.find("div", {"class": "text-right"})
    if not isinstance(size_el, Tag):
        return []
    return re.findall(r'\d{1,4}\sm²', size_el.text)

def is_verified_company(row: Tag) -> bool:
    """Filter out ads from 'Verified Companies'"""
    verified_el = row.find("span", {"class": "label_verified"})
    if isinstance(verified_el, Tag):
        return True
    return False

# pylint: disable=too-many-return-statements
def parse_expose_element_to_details(row: Tag, crawler: str) -> Optional[Dict]:
    """Parse an Expose soup element to an Expose details dictionary"""
    title_row = row.find('h2', {"class": "truncate_title"})
    if title_row is None or not isinstance(title_row, Tag):
        logger.warning("No title found - skipping")
        return None
    if is_verified_company(row):
        logger.warning("Advert found - skipping")
        return None
    title = get_title(title_row)
    url = get_url(title_row)
    if url is None:
        logger.warning("No expose URL found - skipping")
        return None
    image = get_image_url(row)
    rooms = get_rooms(row)
    numbers_row = row.find("div", {"class": "middle"})
    if not isinstance(numbers_row, Tag):
        logger.warning("No numbers row found - skipping")
        return None
    price = get_price(numbers_row)
    dates = get_dates(numbers_row)
    if len(dates) == 0:
        logger.warning("No dates found - skipping")
        return None
    size = get_size(numbers_row)
    if len(size) == 0:
        logger.warning("No size found - skipping")
        return None

    if len(dates) == 2:
        title = f"{title} vom {dates[0]} bis {dates[1]}"
    else:
        title = f"{title} ab dem {dates[0]}"

    details = {
        'id': int(url.split('.')[-2]),
        'image': image,
        'url': url,
        'title': title,
        'price': price,
        'size': size[0],
        'rooms': rooms,
        'address': url,
        'crawler': crawler
    }
    if len(dates) == 2:
        details['from'] = dates[0]
        details['to'] = dates[1]
    elif len(dates) == 1:
        details['from'] = dates[0]
    return details


def liste_attribute_filter(element: Union[Tag, str]) -> bool:
    """Return true for elements whose 'id' attribute starts with 'liste-' 
    and are not contained in the 'premium_user_extra_list' container"""
    if not isinstance(element, Tag):
        return False
    if not element.attrs or "id" not in element.attrs:
        return False
    if not element.parent or not element.parent.attrs or "class" not in element.parent.attrs:
        return False
    return element.attrs["id"].startswith('liste-') and \
        'premium_user_extra_list' not in element.parent.attrs["class"]


class WgGesucht(Crawler):
    """Implementation of Crawler interface for WgGesucht"""

    URL_PATTERN = re.compile(r'https://www\.wg-gesucht\.de')

    def __init__(self, config):
        super().__init__(config)
        self.config = config

    # pylint: disable=too-many-locals
    def extract_data(self, raw_data: BeautifulSoup) -> List[Dict]:
        """Extracts all exposes from a provided Soup object"""
        entries = []

        findings = raw_data.find_all(liste_attribute_filter)
        existing_findings = [
            e for e in findings
            if isinstance(e, Tag) and e.has_attr('class') and not 'display-none' in e['class']
        ]
        for row in existing_findings:
            details = parse_expose_element_to_details(row, self.get_name())
            if details is None:
                continue
            entries.append(details)

        logger.debug('Number of entries found: %d', len(entries))

        return entries

    def load_address(self, url) -> Optional[str]:
        """Extract address from expose itself"""
        response = self.get_soup_from_url(url)
        address_div = response.find('div', {"class": "col-sm-4 mb10"})
        if not isinstance(address_div, Tag):
            logger.debug("No address in response for URL: %s", url)
            return None
        a_element = address_div.find("a", {"href": "#mapContainer"})
        if not isinstance(a_element, Tag):
            logger.debug("No address in response for URL: %s", url)
            return None
        return ' '.join(a_element.text.strip().split())

    def get_soup_from_url(
            self,
            url: str,
            driver: Optional[Any] = None,
            checkbox: bool = False,
            afterlogin_string: Optional[str] = None) -> BeautifulSoup:
        """
        Creates a Soup object from the HTML at the provided URL

        Overwrites the method inherited from abstract_crawler. This is
        necessary as we need to reload the page once for all filters to
        be applied correctly on wg-gesucht.
        """
        sess = requests.session()
        # First page load to set filters; response is discarded
        sess.get(url, headers=self.HEADERS)
        # Second page load
        resp = sess.get(url, headers=self.HEADERS)

        if resp.status_code not in (200, 405):
            logger.error("Got response (%i): %s",
                         resp.status_code, resp.content)
        if self.config.use_proxy():
            return self.get_soup_with_proxy(url)
        if driver is not None:
            driver.get(url)
            if re.search("initGeetest", driver.page_source):
                self.resolve_geetest(driver)
            elif re.search("g-recaptcha", driver.page_source):
                self.resolve_recaptcha(
                    driver, checkbox, afterlogin_string or "")
            return BeautifulSoup(driver.page_source, 'lxml')
        return BeautifulSoup(resp.content, 'lxml')
