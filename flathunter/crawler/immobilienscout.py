"""Expose crawler for ImmobilienScout"""
import re
from urllib.parse import urlencode, urlparse, parse_qs

import requests

from flathunter.abstract_crawler import Crawler
from flathunter.logging import logger
from flathunter.schemas.immobilienscout import ImmoscoutQuery

STATIC_URL_PATTERN = re.compile(r'https://www\.immobilienscout24\.de')

class Immobilienscout(Crawler):
    """Implementation of Crawler interface for ImmobilienScout"""

    URL_PATTERN = STATIC_URL_PATTERN

    HEADERS = {
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "ImmoScout_27.3_26.0_._"
    }

    RESULT_LIMIT = 50

    FALLBACK_IMAGE_URL = "https://www.static-immobilienscout24.de/statpic/placeholder_house/" + \
                         "496c95154de31a357afa978cdb7f15f0_placeholder_medium.png"


    def get_immoscout_query(self, search_url: str) -> ImmoscoutQuery:
        """Builds an Immoscout query from a web interface URL,
        transforms and validates parameters"""
        parsed_url = urlparse(search_url)
        path_elements = parsed_url.path.split("/")

        real_estate_type = path_elements.pop()
        geocodes = None
        if "radius" in path_elements:
            search_type = "radius"
        else:
            search_type = "region"
            geocodes = "/".join(path_elements[2:])
        _ = parse_qs(parsed_url.query)
        query_params: dict[str, str | list[str]] = {}
        # split comma-separated query param values into list
        for k in _: # pylint: disable=consider-using-dict-items
            query_params[k] = [v for value in _[k] for v in value.split(",")]
            # unpack single item lists unless ImmoscoutQuery expects a list
            if len(query_params[k]) == 1 and k not in (
                "apartmenttypes",
                "energyefficiencyclasses",
                "equipment",
                "exclusioncriteria",
                "heatingtypes",
                "petsallowedtypes"
            ):
                query_params[k] = query_params[k][0]
        return ImmoscoutQuery(
            realestatetype=real_estate_type, # type: ignore
            searchtype=search_type,
            geocodes=geocodes,
            # set pagesize to result limit to minimize number of API requests
            pagesize=self.RESULT_LIMIT,
            **query_params # type: ignore
        )

    def compose_api_url(self, query: ImmoscoutQuery) -> str:
        """Constructs a mobile API URL from an Immoscout query"""
        api_url = "https://api.mobile.immobilienscout24.de/search/list?"
        query_dict = query.model_dump(exclude_none=True)
        for k, v in query_dict.items():
            # join list items to comma-separated query parameter string
            if isinstance(v, list):
                query_dict[k] = ",".join(v)
        return api_url + urlencode(query_dict)

    def fetch_api_data(self, search_url: str, page_no: int | None = None) -> requests.Response:
        """Applies a page number to a formatted API URL and fetches the exposes at that page"""

        data = {
            "supportedResultListType": [],
            "userData": {}
        }
        response = requests.post(
            search_url.format(page_no),
            headers=self.HEADERS,
            json=data,
            timeout=30
        )
        return response

    def extract_data(self, raw_data: dict) -> list:
        """Extracts all exposes from a JSON dictionary"""
        entries = []

        results = filter(
            lambda entry: entry.get("type") == "EXPOSE_RESULT",
            raw_data.get("resultListItems") or []
        )
        for expose in results:
            expose_details = expose.get("item")
            details = {
                'id': int(expose_details.get("id")),
                'url': "https://www.immobilienscout24.de/expose/" + expose_details.get("id"),
                # remove height and width parameters from image URL
                'image': re.sub(
                    r"(.+?(?:\.(?:jpe?g|png))).*",
                    r"\1",
                    expose_details.get("titlePicture", {}).get("preview", self.FALLBACK_IMAGE_URL),
                    flags=re.IGNORECASE
                ),
                'title': expose_details.get("title", ""),
                'address': expose_details.get("address", {}).get("line", ""),
                'crawler': self.get_name()
            }
            flat_attributes = [
                attribute.get("value") for attribute in expose_details.get("attributes")
            ]
            for attr in flat_attributes:
                if "€" in attr:
                    details["price"] = attr.replace("\xa0€", "")
                elif "m²" in attr:
                    details["size"] = attr.replace("\xa0m²", "")
                elif "Zi." in attr:
                    details["rooms"] = attr.replace("\xa0Zi.", "")
            entries.append(details)

        logger.debug('Number of entries found: %d', len(entries))
        return entries

    def get_results(self, search_url: str, max_pages: int | None = None) -> list:
        """Fetches the exposes from the ImmoScout mobile API, starting at the provided URL"""
        query = self.get_immoscout_query(search_url)
        api_url = self.compose_api_url(query)
        if '&pagenumber' in api_url:
            api_url = re.sub(r"&pagenumber=[0-9]", "&pagenumber={0}", api_url)
        else:
            api_url = api_url + '&pagenumber={0}'
        logger.debug("Got search URL %s", api_url)

        page_no = 1
        listings = self.fetch_api_data(api_url, page_no).json()

        no_of_results = listings["totalResults"]

        # get data from first page
        entries = self.extract_data(listings)

        # iterate over all remaining pages
        while len(entries) < min(no_of_results, self.RESULT_LIMIT) and \
                (max_pages is None or page_no < max_pages):
            logger.debug(
                '(Next page) Number of entries: %d / Number of results: %d',
                len(entries), no_of_results)
            page_no += 1
            listings = self.fetch_api_data(api_url, page_no).json()
            cur_entries = self.extract_data(listings)
            entries.extend(cur_entries)
        return entries
