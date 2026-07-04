import re, json, hashlib
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from bs4 import BeautifulSoup
from flathunter.logging import logger
from flathunter.abstract_crawler import Crawler

class InBerlinWohnen(Crawler):
    BASE_URL = "https://www.inberlinwohnen.de"
    URL_PATTERN = re.compile(r'https://www\.inberlinwohnen\.de')

    def __init__(self, config):
        super().__init__(config)

    def get_page(self, search_url, driver=None, page_no=None):
        # Replace page param in URL if page_no is given
        if page_no:
            parsed_url = urlparse(search_url)
            query_params = parse_qs(parsed_url.query)
            query_params['page'] = [str(page_no)]
            new_query = urlencode(query_params, doseq=True)
            new_url = urlunparse((
                parsed_url.scheme,
                parsed_url.netloc,
                parsed_url.path,
                parsed_url.params,
                new_query,
                parsed_url.fragment
            ))
            search_url = new_url
        return self.get_soup_from_url(search_url)

    def get_results(self, search_url, max_pages=None):
        # Fetch page 1 to get total count
        soup = self.get_page(search_url, page_no=1)

        # Get all entries from page 1
        entries = self.extract_data(soup)

        # Find total pages
        total_pages = self._get_total_pages(soup)

        if max_pages:
            total_pages = min(total_pages, max_pages)

        # Fetch remaining pages
        for page_no in range(2, total_pages + 1):
            logger.debug("Crawling page %d", page_no)
            soup = self.get_page(search_url, page_no=page_no)
            entries.extend(self.extract_data(soup))

        return entries

    def _get_total_pages(self, soup):
        # Find pagination div and extract total count
        pagination_div = soup.find('div', class_='pagination')
        if not pagination_div:
            return 1

        p_tag = pagination_div.find('p')
        if not p_tag:
            return 1

        text = p_tag.get_text()
        match = re.search(r'von (\d+) Angeboten', text)
        if not match:
            return 1

        total = int(match.group(1))
        # Assuming 10 items per page
        pages = (total + 9) // 10  # Ceiling division
        return pages

    def extract_data(self, soup):
        entries = []

        # Step 1: Build deeplinks dict from wire:snapshot elements
        deeplinks = {}
        snapshot_elements = soup.find_all(attrs={'wire:snapshot': True})
        for element in snapshot_elements:
            try:
                snapshot_json = json.loads(element['wire:snapshot'])
                if 'memo' in snapshot_json and 'name' in snapshot_json['memo']:
                    if snapshot_json['memo']['name'] == "apartment-finder.item.partials.deeplink-button":
                        flat_id = snapshot_json['data'].get('flatId')
                        deeplink = snapshot_json['data'].get('deeplink')
                        if flat_id and deeplink:
                            deeplinks[flat_id] = deeplink
            except (json.JSONDecodeError, KeyError):
                continue

        # Step 2: Iterate over listing rows
        listing_elements = soup.find_all('span', attrs={'wire:snapshot': True})
        for element in listing_elements:
            try:
                snapshot_json = json.loads(element['wire:snapshot'])
                if 'memo' in snapshot_json and 'name' in snapshot_json['memo']:
                    if snapshot_json['memo']['name'] == "apartment-finder.item.partials.collapsible-apartment-title":
                        # Extract flat data
                        flat_data = snapshot_json['data']
                        item_id = flat_data.get('itemId')
                        rooms = flat_data.get('rooms', '')
                        area = flat_data.get('area', '')
                        rent_net = flat_data.get('rentNet', '')
                        street = flat_data.get('street', '')
                        number = flat_data.get('number', '')
                        zip_code = flat_data.get('zipCode', '')
                        district = flat_data.get('district', '')

                        if item_id:
                            # Build address
                            address_parts = [street, number, zip_code, district]
                            address = ', '.join(part for part in address_parts if part)

                            # Get price (rent net + 10% for utilities, or just rent net)
                            price = f"{rent_net} €"

                            # Get size
                            size = f"{area} m²" if area else ""

                            # Look up the deeplink URL
                            url = deeplinks.get(item_id, '')

                            # Get image and title from detail card
                            image_url, title = self._get_image_and_title(soup, item_id)

                            # Build expose dict
                            expose = {
                                'id': int(hashlib.sha256(str(item_id).encode()).hexdigest(), 16) % (10**16),
                                'image': image_url,
                                'url': url,
                                'title': title,
                                'rooms': rooms,
                                'price': price,
                                'size': size,
                                'address': address,
                                'crawler': self.get_name()
                            }

                            entries.append(expose)
            except (json.JSONDecodeError, KeyError):
                continue

        return entries

    def _get_image_and_title(self, soup, flat_id):
        # Find detail card for this apartment
        detail_card = soup.find(attrs={'x-ref': f'apartment-{flat_id}'})
        if not detail_card:
            return '', ''

        image_url = ''
        title = ''

        # Extract image
        img_element = detail_card.find('img', alt='Wohnungsbild')
        if img_element and img_element.get('src'):
            src = img_element['src']
            if src.startswith('/'):
                image_url = f"{self.BASE_URL}{src}"
            else:
                image_url = src

        # Extract title
        title_element = detail_card.find('span', class_='my-7')
        if title_element:
            title = title_element.get_text(strip=True)

        return image_url, title