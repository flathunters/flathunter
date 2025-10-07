import pytest
from time import sleep

from flathunter.crawler.immobilienscout import Immobilienscout
from test.utils.config import StringConfig

DUMMY_CONFIG = """
urls:
  - https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten?enteredFrom=one_step_search
"""


TEST_URLS = [
  (
    "https://www.immobilienscout24.de/Suche"
    "/de/berlin/berlin/neubauwohnung-mieten?"
    "heatingtypes=central,selfcontainedcentral"
    "&haspromotion=false"
    "&numberofrooms=1.0-6.0"
    "&livingspace=20.0-140.0"
    "&energyefficiencyclasses=a,b,c,d,e,f,g,h,a_plus"
    "&exclusioncriteria=swapflat,projectlisting"
    "&minimuminternetspeed=100000"
    "&equipment=parking,cellar,handicappedaccessible,builtinkitchen,lift,garden,guesttoilet,balcony"
    "&petsallowedtypes=no,yes,negotiable"
    "&price=200.0-4000.0"
    "&constructionyear=1920-2020"
    "&apartmenttypes=halfbasement,penthouse,other,loft,groundfloor,terracedflat,raisedgroundfloor,apartment,roofstorey,maisonette"
    "&pricetype=rentpermonth"
    "&floor=1-20"
    "&enteredFrom=result_list"
  ),
  (
    "https://www.immobilienscout24.de/Suche"
    "/de/berlin/berlin/neubauwohnung-mieten?"
    "pricetype=rentpermonth"
    "&enteredFrom=result_list"
    "&sorting=10"
  ),
  (
    "https://www.immobilienscout24.de/Suche"
    "/radius/wohnung-mieten?"
    "centerofsearchaddress=Berlin;;;;;;"
    "&pricetype=rentpermonth"
    "&geocoordinates=52.52343;13.41144;5.0"
    "&enteredFrom=result_list"
  )
]

TEST_API_URLS = [
  (
    "https://api.mobile.immobilienscout24.de/search/list?"
    "apartmenttypes=halfbasement%2Cpenthouse%2Cother%2Cloft%2Cgroundfloor%2Cterracedflat%2Craisedgroundfloor%2Capartment%2Croofstorey%2Cmaisonette"
    "&constructionyear=1920-2020"
    "&energyefficiencyclasses=a%2Cb%2Cc%2Cd%2Ce%2Cf%2Cg%2Ch%2Ca_plus"
    "&equipment=parking%2Ccellar%2Chandicappedaccessible%2Cbuiltinkitchen%2Clift%2Cgarden%2Cguesttoilet%2Cbalcony"
    "&exclusioncriteria=swapflat%2Cprojectlisting"
    "&floor=1-20"
    "&geocodes=de%2Fberlin%2Fberlin"
    "&haspromotion=false"
    "&heatingtypes=central%2Cselfcontainedcentral"
    "&livingspace=20.0-140.0"
    "&minimuminternetspeed=100000"
    "&newbuilding=true"
    "&numberofrooms=1.0-6.0"
    "&pagenumber=1"
    "&pagesize=50"
    "&petsallowedtypes=no%2Cyes%2Cnegotiable"
    "&price=200.0-4000.0"
    "&pricetype=rentpermonth"
    "&realestatetype=apartmentrent"
    "&searchType=region"
    "&sorting=-firstactivation"
  ),
  (
    "https://api.mobile.immobilienscout24.de/search/list?"
    "geocodes=de%2Fberlin%2Fberlin"
    "&newbuilding=true"
    "&pagenumber=1"
    "&pagesize=50"
    "&pricetype=rentpermonth"
    "&realestatetype=apartmentrent"
    "&searchType=region"
    "&sorting=-firstactivation"
  ),
  (
    "https://api.mobile.immobilienscout24.de/search/list?"
    "geocoordinates=52.52343%3B13.41144%3B5.0"
    "&pagenumber=1"
    "&pagesize=50"
    "&pricetype=rentpermonth"
    "&realestatetype=apartmentrent"
    "&searchType=radius"
    "&sorting=-firstactivation"
  )
]

test_config = StringConfig(string=DUMMY_CONFIG)

@pytest.fixture
def crawler():
    return Immobilienscout(test_config)

@pytest.mark.parametrize("test_url, test_api_url", zip(TEST_URLS, TEST_API_URLS))
def test_url_conversion(crawler, test_url, test_api_url):
    query = crawler.get_immoscout_query(test_url)
    api_url = crawler.compose_api_url(query)
    assert api_url == test_api_url

@pytest.mark.parametrize("test_api_url", TEST_API_URLS)
def test_api_response(crawler, test_api_url):
  response = crawler.fetch_api_data(test_api_url)
  assert response.status_code == 200
  # throttle to not flood api
  sleep(1)

def test_extract_data_from_response(crawler):
  entries = crawler.get_results(crawler.config.target_urls()[0])
  required_keys = {
    "id",
    "url",
    "image",
    "title",
    "address",
    "crawler",
    "price",
    "size",
    "rooms"
  }
  assert entries
  for entry in entries:
    assert required_keys == entry.keys()
