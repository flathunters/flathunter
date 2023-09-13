import os
import unittest
from functools import reduce

from flathunter.crawler.vrmimmo import VrmImmo
from test.utils.config import StringConfig

class VrmImmoCrawlerTest(unittest.TestCase):
    TEST_URL = 'https://vrm-immo.de/suchergebnisse?l=Darmstadt&r=0km&_multiselect_r=0km&a=de.darmstadt&t=apartment%3Asale%3Aliving&pf=&pt=&rf=0&rt=0&sf=&st=&s=most_recently_updated_first'
    DUMMY_CONFIG = """
    verbose: true
    urls:
      - https://vrm-immo.de/suchergebnisse?l=Darmstadt&r=0km&_multiselect_r=0km&a=de.darmstadt&t=all%3Arental%3Aliving&pf=&pt=&rf=0&rt=0&sf=&st=
        """

    def setUp(self):
        self.crawler = VrmImmo(StringConfig(string=self.DUMMY_CONFIG))

    def test(self):
        soup = self.crawler.get_page(self.TEST_URL)
        self.assertIsNotNone(soup, "Should get a soup from the URL")
        entries = self.crawler.extract_data(soup)
        self.assertIsNotNone(entries, "Should parse entries from search URL")
        self.assertTrue(len(entries) > 0, "Should have at least one entry")
        self.assertTrue(entries[0]['id'] > 0, "Id should be parsed")
        self.assertTrue(entries[0]['url'].startswith("https://vrm-immo.de"), u"URL should start with BASE_URL")
        self.assertTrue(entries[0]['url'].startswith("https://vrm-immo.de/immobilien"),
                        u"URL should be an immobilien link")
        for attr in ['title', 'price', 'size', 'rooms', 'address', 'image']:
            self.assertIsNotNone(entries[0][attr], attr + " should be set")
