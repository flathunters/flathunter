import unittest
import datetime
import re
from typing import Dict

from flathunter.idmaintainer import IdMaintainer
from flathunter.hunter import Hunter
from flathunter.web_hunter import WebHunter
from flathunter.filter import FilterChain
from flathunter.dataclasses import FilterChainName
from test.dummy_crawler import DummyCrawler
from test.test_util import count
from test.utils.config import StringConfig

class IdMaintainerTest(unittest.TestCase):

    TEST_URL = 'https://www.immowelt.de/liste/berlin/wohnungen/mieten?roomi=2&prima=1500&wflmi=70&sort=createdate%2Bdesc'

    DUMMY_CONFIG = """
urls:
  - https://www.example.com/liste/berlin/wohnungen/mieten?roomi=2&prima=1500&wflmi=70&sort=createdate%2Bdesc
    """

    CONFIG_WITH_FILTERS = """
urls:
  - https://www.example.com/liste/berlin/wohnungen/mieten?roomi=2&prima=1500&wflmi=70&sort=createdate%2Bdesc

filters:
  max_price: 1000
    """

    def setUp(self):
        self.maintainer = IdMaintainer(":memory:")

    def test_read_after_write(self):
        self.maintainer.mark_processed(12345)
        self.assertTrue(self.maintainer.is_processed(12345), "Expected ID to be saved")

    def test_get_last_run_time_none_by_default(self):
        self.assertIsNone(self.maintainer.get_last_run_time(), "Expected last run time to be none")

    def test_get_list_run_time_is_updated(self):
        time = self.maintainer.update_last_run_time()
        self.assertIsNotNone(time, "Expected time not to be none")
        self.assertEqual(time, self.maintainer.get_last_run_time(), "Expected last run time to be updated")

def test_is_processed_works(mocker):
    config = StringConfig(string=IdMaintainerTest.DUMMY_CONFIG)
    config.set_searchers([DummyCrawler()])
    id_watch = IdMaintainer(":memory:")
    hunter = Hunter(config, id_watch)
    exposes = hunter.hunt_flats()
    assert count(exposes) > 4
    for expose in exposes:
        assert id_watch.is_processed(expose['id'])

def test_ids_are_added_to_maintainer(mocker):
    config = StringConfig(string=IdMaintainerTest.DUMMY_CONFIG)
    config.set_searchers([DummyCrawler()])
    id_watch = IdMaintainer(":memory:")
    spy = mocker.spy(id_watch, "mark_processed")
    hunter = Hunter(config, id_watch)
    exposes = hunter.hunt_flats()
    assert count(exposes) > 4
    assert spy.call_count == 24

def test_exposes_are_saved_to_maintainer():
    config = StringConfig(string=IdMaintainerTest.CONFIG_WITH_FILTERS)
    config.set_searchers([DummyCrawler()])
    id_watch = IdMaintainer(":memory:")
    hunter = Hunter(config, id_watch)
    exposes = hunter.hunt_flats()
    assert count(exposes) > 4
    saved = id_watch.get_exposes_since(datetime.datetime.now() - datetime.timedelta(seconds=10))
    assert len(saved) > 0
    assert count(exposes) < len(saved)

def test_exposes_are_returned_as_dictionaries():
    config = StringConfig(string=IdMaintainerTest.CONFIG_WITH_FILTERS)
    config.set_searchers([DummyCrawler()])
    id_watch = IdMaintainer(":memory:")
    hunter = Hunter(config, id_watch)
    hunter.hunt_flats()
    saved = id_watch.get_exposes_since(datetime.datetime.now() - datetime.timedelta(seconds=10))
    assert len(saved) > 0
    expose = saved[0]
    assert expose['title'] is not None
    assert expose['created_at'] is not None

def test_exposes_are_returned_with_limit():
    config = StringConfig(string=IdMaintainerTest.CONFIG_WITH_FILTERS)
    config.set_searchers([DummyCrawler()])
    id_watch = IdMaintainer(":memory:")
    hunter = Hunter(config, id_watch)
    hunter.hunt_flats()
    saved = id_watch.get_recent_exposes(10)
    assert len(saved) == 10
    expose = saved[0]
    assert expose['title'] is not None

def compare_int_less_equal(expose: Dict, key: str, comparison: int) -> bool:
    value = expose.get(key, str(comparison + 1))
    match = re.match(r'\d+', value)
    if match is None:
        return False
    return int(match[0]) <= comparison

def test_exposes_are_returned_filtered():
    config = StringConfig(string=IdMaintainerTest.CONFIG_WITH_FILTERS)
    config.set_searchers([DummyCrawler()])
    id_watch = IdMaintainer(":memory:")
    hunter = Hunter(config, id_watch)
    hunter.hunt_flats()
    hunter.hunt_flats()
    filter = (FilterChain
            .builder()
            .read_config(StringConfig('{"filters":{"max_size":70}}'), FilterChainName.preprocess)
            .build())
    saved = id_watch.get_recent_exposes(10, filter_set=filter)
    assert len(saved) == 10
    for expose in saved:
        assert compare_int_less_equal(expose, 'size', 70)

def test_filters_for_user_are_saved():
    config = StringConfig(string=IdMaintainerTest.CONFIG_WITH_FILTERS)
    id_watch = IdMaintainer(":memory:")
    filter = { 'fish': 'cat' }
    hunter = WebHunter(config, id_watch)
    hunter.set_filters_for_user(123, filter)
    assert hunter.get_filters_for_user(123) == filter

def test_all_filters_can_be_loaded():
    config = StringConfig(string=IdMaintainerTest.CONFIG_WITH_FILTERS)
    id_watch = IdMaintainer(":memory:")
    filter = { 'fish': 'cat' }
    hunter = WebHunter(config, id_watch)
    hunter.set_filters_for_user(123, filter)
    hunter.set_filters_for_user(124, filter)
    assert id_watch.get_user_settings() == [ (123, { 'filters': filter }), (124, { 'filters': filter }) ]
