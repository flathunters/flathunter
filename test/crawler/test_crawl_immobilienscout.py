import pytest
import json
import os
import requests_mock
import re

from flathunter.crawler.immobilienscout import Immobilienscout
from flathunter.captcha.twocaptcha_solver import TwoCaptchaSolver
from flathunter.captcha.captcha_solver import CaptchaBalanceEmpty
from test.utils.config import StringConfigWithCaptchas

DUMMY_CONFIG = """
urls:
  - https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten?numberofrooms=2.0-&price=-1500.0&livingspace=70.0-&sorting=2&pagenumber=1
    """


TEST_URL = 'https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten?numberofrooms=2.0-&price=-1500.0&livingspace=70.0-&sorting=2&pagenumber=1'

test_config = StringConfigWithCaptchas(string=DUMMY_CONFIG)

@pytest.fixture
def crawler():
    return Immobilienscout(test_config)

def test_parse_exposes_from_json(crawler):
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "fixtures", "immo-scout-IS24-object.json")) as fixture:
        data = json.load(fixture)
    entries = crawler.get_entries_from_json(data)
    assert len(entries) > 0

def test_crawl_works(crawler):
    if not test_config.captcha_enabled():
        pytest.skip("Captcha solving is not enabled - skipping immoscout tests. Setup captcha solving")
    soup = crawler.get_page(TEST_URL, crawler.get_driver(), page_no=1)
    assert soup is not None
    print(soup)
    entries = crawler.extract_data(soup)
    assert entries is not None
    assert len(entries) > 0
    assert entries[0]['id'] > 0
    assert entries[0]['url'].startswith("https://www.immobilienscout24.de/expose")
    for attr in [ 'title', 'price', 'size', 'rooms', 'address' ]:
        assert entries[0][attr] is not None

def test_process_expose_fetches_details(crawler):
    if not test_config.captcha_enabled():
        pytest.skip("Captcha solving is not enabled - skipping immoscout tests. Setup captcha solving")
    soup = crawler.get_page(TEST_URL, crawler.get_driver(), page_no=1)
    assert soup is not None
    entries = crawler.extract_data(soup)
    assert entries is not None
    assert len(entries) > 0
    updated_entries = [ crawler.get_expose_details(expose) for expose in entries ]
    for expose in updated_entries:
        for attr in [ 'title', 'price', 'size', 'rooms', 'address' ]:
            assert expose[attr] is not None

def test_twocaptcha_error_no_balance(crawler):
    if not test_config.captcha_enabled():
        pytest.skip("Captcha solving is not enabled - skipping immoscout tests. Setup captcha solving")
    if not isinstance(test_config.get_captcha_solver(), TwoCaptchaSolver):
        pytest.skip("Captcha solver is not 2captcha - skipping 2captcha balance check")
    with requests_mock.mock() as m:
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "fixtures", "immo-scout-IS24-response.html")) as fixture:
            immo_scout_matcher = re.compile('www.immobilienscout24.de')
            m.get(immo_scout_matcher, text=fixture.read())
        m.post('http://2captcha.com/in.php', text='OK|asdfkjhsdf')
        m.get('http://2captcha.com/res.php', text='ERROR_ZERO_BALANCE')
        with pytest.raises(CaptchaBalanceEmpty):
            assert crawler.get_page(TEST_URL, crawler.get_driver(), page_no=1)
