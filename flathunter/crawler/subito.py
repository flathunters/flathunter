"""Expose crawler for Subito"""
import re
import json

from flathunter.logging import logger
from flathunter.abstract_crawler import Crawler

class Subito(Crawler):
    """Implementation of Crawler interface for Subito"""

    URL_PATTERN = re.compile(r'https://www\.subito\.it')

    def __init__(self, config):
        super().__init__(config)
        self.config = config

    # pylint: disable=too-many-locals
    def extract_data(self, raw_data):
        """Extracts all exposes from a provided Soup object"""
        entries = []

        # as of today, subito provides a useful JSON that represents the state
        # of the search. Neat! We don't have to do much.
        findings_json = raw_data.find("script", {"id": "__NEXT_DATA__"}).text.strip()
        findings = json.loads(findings_json)["props"]["state"]["items"]["list"]

        for row in findings:
            row_id = row["item"]["urn"]
            title = row["item"]["subject"]

            # some advertisements sneak in their search for apartments into
            # the rent section, so we skip them
            if re.match(r"cerco", title, re.IGNORECASE):
                continue
            url = row["item"]["urls"]["default"]
            images = row["item"]["images"]

            # we get the first image available. According to the structure
            # there is the possibility to have different image sizes (small, slider,
            # medium...), but we will just get the first one if available.
            image = images[4]["scale"][4]["secureuri"] if len(images) > 4 else ""

            features = row["item"]["features"]

            price = features["/price"]["values"][0]["key"] if "/price" in features else "?"
            rooms = features["/room"]["values"][0]["key"] if "/room" in features else "?"
            size = features["/size"]["values"][0]["key"] if "/size" in features else "?"

            # Unfortunately, Subito does not give the full address, so we'll just have to work
            # with what we got and be happy with the address
            geo = row["item"]["geo"]
            town = geo["town"]["value"] if geo["town"] else ""
            city = geo["city"]["shortName"] if geo["city"] else ""
            region = geo["region"]["value"] if geo["region"] else ""
            address = f"{town}, {city}, {region}"

            details = {
                'id': re.sub(r"[^0-9]", "", row_id),
                # the image is correct... however for some reason they don't show up
                # in telegram's thumbnail
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

        logger.debug('Number of found entries: %d', len(entries))

        return entries
