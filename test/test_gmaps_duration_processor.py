from typing import Dict
import unittest
import re
from flathunter.gmaps_duration_processor import DistanceElement
import requests_mock
from flathunter.hunter import Hunter
from flathunter.idmaintainer import IdMaintainer
from test.dummy_crawler import DummyCrawler
from test.test_util import count
from test.utils.config import StringConfig

class GMapsDurationProcessorTest(unittest.TestCase):

    DUMMY_CONFIG = """
urls:
  - https://www.example.com/liste/berlin/wohnungen/mieten?roomi=2&prima=1500&wflmi=70&sort=createdate%2Bdesc

google_maps_api:
  key: SOME_KEY
  url: https://maps.googleapis.com/maps/api/distancematrix/json?origins={origin}&destinations={dest}&mode={mode}&sensor=true&key={key}&arrival_time={arrival}
  enable: true

durations:
  - destination: Buckingham Palace UK
    name: The Queen
    modes:
      - gm_id: transit
        title: By Bus
  - destination: главная площадь
    name: Москва
    modes:
      - gm_id: bicycling
        title: Bicyle
      - gm_id: driving
        title: Car
    """
    DUMMY_RESPONSE = """
    {
      "status": "OK",
      "rows": [
        {
          "elements": [
            {
              "distance": { "text": "228 mi", "value": 367654 },
              "duration": { "text": "3 hours 55 mins", "value": 14078 }
            }
          ]
        }
      ]
    }"""

    @requests_mock.Mocker()
    def test_resolve_durations(self, m):
        config = StringConfig(string=self.DUMMY_CONFIG)
        config.set_searchers([DummyCrawler()])
        hunter = Hunter(config, IdMaintainer(":memory:"))
        matcher = re.compile('maps.googleapis.com/maps/api/distancematrix/json')
        m.get(matcher, text=self.DUMMY_RESPONSE)
        exposes = hunter.hunt_flats()
        self.assertTrue(count(exposes) > 4, "Expected to find exposes")
        without_durations = list(filter(lambda expose: 'durations' not in expose, exposes))
        for expose in without_durations:
            print("Got expose: ", expose)
        self.assertTrue(len(without_durations) == 0, "Expected durations to be calculated")
    
    @requests_mock.Mocker()
    def test_durations_valid(self, m):
        config = StringConfig(string=self.DUMMY_CONFIG)
        config.set_searchers([DummyCrawler()])
        hunter = Hunter(config, IdMaintainer(":memory:"))
        matcher = re.compile('maps.googleapis.com/maps/api/distancematrix/json')
        m.get(matcher, text=self.DUMMY_RESPONSE)
        exposes = hunter.hunt_flats()
        for expose in exposes:
            durations: Dict[str, DistanceElement] = expose['durations_unformatted']
            for duration in durations.values():
                self.assertAlmostEqual(duration.distance.meters, 367654)
                self.assertAlmostEqual(duration.duration.seconds, 14078)
                self.assertEqual(duration.duration.text, '3 hours 55 mins')
