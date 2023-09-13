import unittest
import tempfile
import os.path
import os
from flathunter.config import Config
from test.utils.config import StringConfig

class ConfigTest(unittest.TestCase):

    DUMMY_CONFIG = """
urls:
  - https://www.immowelt.de/liste/berlin/wohnungen/mieten?roomi=2&prima=1500&wflmi=70&sort=createdate%2Bdesc
    """

    EMPTY_FILTERS_CONFIG = """
urls:
  - https://www.immowelt.de/liste/berlin/wohnungen/mieten?roomi=2&prima=1500&wflmi=70&sort=createdate%2Bdesc

filters:

"""

    LEGACY_FILTERS_CONFIG = """
urls:
  - https://www.immowelt.de/liste/berlin/wohnungen/mieten?roomi=2&prima=1500&wflmi=70&sort=createdate%2Bdesc

excluded_titles:
  - Title
  - Another
"""

    FILTERS_CONFIG = """
urls:
  - https://www.immowelt.de/liste/berlin/wohnungen/mieten?roomi=2&prima=1500&wflmi=70&sort=createdate%2Bdesc

filters:
    excluded_titles:
        - fish
    min_size: 30
    max_size: 100
    min_price: 500
    max_price: 1500
    min_rooms: 2
    max_rooms: 5
"""

    def test_loads_config(self):
        created = False
        if not os.path.isfile("config.yaml"):
            config_file = open("config.yaml", "w")
            config_file.write(self.DUMMY_CONFIG)
            config_file.flush()
            config_file.close()
            created = True
        config = Config("config.yaml")
        self.assertTrue(len(config.get('urls', [])) > 0, "Expected URLs in config file")
        if created:
            os.remove("config.yaml")

    def test_loads_config_at_file(self):
       tempFileName = None
       try:
         with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp:
            temp.write(self.DUMMY_CONFIG)
            temp.flush()
            tempFileName = temp.name
         config = Config(tempFileName) 
         self.assertTrue(len(config.get('urls', [])) > 0, "Expected URLs in config file")
       finally:
         os.unlink(tempFileName)

    def test_loads_config_from_string(self):
       config = StringConfig(string=self.EMPTY_FILTERS_CONFIG)
       self.assertIsNotNone(config)
       my_filter = config.get_filter()
       self.assertIsNotNone(my_filter)

    def test_loads_legacy_config_from_string(self):
       config = StringConfig(string=self.LEGACY_FILTERS_CONFIG)
       self.assertIsNotNone(config)
       my_filter = config.get_filter()
       self.assertIsNotNone(my_filter)
       self.assertTrue(len(my_filter.filters) > 0)

    def test_loads_filters_config_from_string(self):
       config = StringConfig(string=self.FILTERS_CONFIG)
       self.assertIsNotNone(config)
       my_filter = config.get_filter()
       self.assertIsNotNone(my_filter)

    def test_defaults_fields(self):
       config = StringConfig(string=self.FILTERS_CONFIG)
       self.assertIsNotNone(config)
       self.assertEqual(config.database_location(), os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + "/.."))
