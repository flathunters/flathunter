"""Interface for webcrawlers. Crawler implementations should subclass this"""
from abc import ABC
import re
from time import sleep
from typing import Optional, Any
import json

import backoff
import requests
# pylint: disable=unused-import
import requests_random_user_agent

from bs4 import BeautifulSoup

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from flathunter import proxies
from flathunter.captcha.captcha_solver import CaptchaUnsolvableError
from flathunter.logging import logger
from flathunter.exceptions import ProxyException


class Crawler(ABC):
    """Defines the Crawler interface"""

    URL_PATTERN: re.Pattern

    HEADERS = {
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
        'Upgrade-Insecure-Requests': '1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;'
                  'q=0.9,image/webp,image/apng,*/*;q=0.8,'
                  'application/signed-exchange;v=b3;q=0.9',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Sec-Fetch-Dest': 'document',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    def __init__(self, config):
        self.config = config
        if config.captcha_enabled():
            self.captcha_solver = config.get_captcha_solver()

    # pylint: disable=unused-argument
    def get_page(self, search_url, driver=None, page_no=None) -> BeautifulSoup:
        """Applies a page number to a formatted search URL and fetches the exposes at that page"""
        return self.get_soup_from_url(search_url)

    @backoff.on_exception(wait_gen=backoff.constant,
                          exception=TimeoutException,
                          max_tries=3)
    def get_soup_from_url(
            self,
            url: str,
            driver: Optional[Any] = None,
            checkbox: bool = False,
            afterlogin_string: Optional[str] = None) -> BeautifulSoup:
        """Creates a Soup object from the HTML at the provided URL"""

        if self.config.use_proxy():
            return self.get_soup_with_proxy(url)
        if driver is not None:
            driver.get(url)
            if re.search("initGeetest", driver.page_source):
                self.resolve_geetest(driver)
            elif re.search("awswaf-captcha", driver.page_source):
                self.resolve_awsawf(driver)
            elif re.search("g-recaptcha", driver.page_source):
                self.resolve_recaptcha(
                    driver, checkbox, afterlogin_string or "")
            return BeautifulSoup(driver.page_source, 'lxml')

        resp = requests.get(url, headers=self.HEADERS, timeout=30)
        if resp.status_code not in (200, 405):
            user_agent = 'Unknown'
            if 'User-Agent' in self.HEADERS:
                user_agent = self.HEADERS['User-Agent']
            logger.error("Got response (%i): %s\n%s",
                         resp.status_code, resp.content, user_agent)

        return BeautifulSoup(resp.content, 'lxml')

    def get_soup_with_proxy(self, url) -> BeautifulSoup:
        """Will try proxies until it's possible to crawl and return a soup"""
        resolved = False
        resp = None

        # We will keep trying to fetch new proxies until one works
        while not resolved:
            proxies_list = proxies.get_proxies()
            for proxy in proxies_list:
                try:
                    # Very low proxy read timeout, or it will get stuck on slow proxies
                    resp = requests.get(
                        url,
                        headers=self.HEADERS,
                        proxies={"http": proxy, "https": proxy},
                        timeout=(20, 0.1)
                    )

                    if resp.status_code != 200:
                        logger.error("Got response (%i): %s",
                                     resp.status_code, resp.content)
                    else:
                        resolved = True
                        break

                except requests.exceptions.ConnectionError:
                    logger.error(
                        "Connection failed for proxy %s. Trying new proxy...", proxy)
                except requests.exceptions.Timeout:
                    logger.error(
                        "Connection timed out for proxy %s. Trying new proxy...", proxy
                    )
                except requests.exceptions.RequestException:
                    logger.error("Some error occurred. Trying new proxy...")

        if not resp:
            raise ProxyException(
                "An error occurred while fetching proxies or content")

        return BeautifulSoup(resp.content, 'lxml')

    def extract_data(self, raw_data):
        """Should be implemented in subclass"""
        raise NotImplementedError

    # pylint: disable=unused-argument
    def get_results(self, search_url, max_pages=None):
        """Loads the exposes from the site, starting at the provided URL"""
        logger.debug("Got search URL %s", search_url)

        # load first page
        soup = self.get_page(search_url)

        # get data from first page
        entries = self.extract_data(soup)
        logger.debug('Number of found entries: %d', len(entries))

        return entries

    def crawl(self, url, max_pages=None):
        """Load as many exposes as possible from the provided URL"""
        if re.search(self.URL_PATTERN, url):
            try:
                return self.get_results(url, max_pages)
            except requests.exceptions.ConnectionError:
                logger.warning(
                    "Connection to %s failed. Retrying.", url.split('/')[2])
                return []
        return []

    def get_name(self):
        """Returns the name of this crawler"""
        return type(self).__name__

    def get_expose_details(self, expose):
        """Loads additional detalis for an expose. Should be implemented in the subclass"""
        return expose

    @backoff.on_exception(wait_gen=backoff.constant,
                          exception=CaptchaUnsolvableError,
                          max_tries=3)
    def resolve_geetest(self, driver):
        """Resolve GeeTest Captcha"""
        data = re.findall(
            "geetest_validate: obj.geetest_validate,\n.*?data: \"(.*)\"",
            driver.page_source
        )[0]
        result = re.findall(
            r"initGeetest\({(.*?)}", driver.page_source, re.DOTALL)

        geetest = re.findall("gt: \"(.*?)\"", result[0])[0]
        challenge = re.findall("challenge: \"(.*?)\"", result[0])[0]
        try:
            captcha_response = self.captcha_solver.solve_geetest(
                geetest,
                challenge,
                driver.current_url
            )
            script = (f'solvedCaptcha({{geetest_challenge: "{captcha_response.challenge}",'
                      f'geetest_seccode: "{captcha_response.sec_code}",'
                      f'geetest_validate: "{captcha_response.validate}",'
                      f'data: "{data}"}});')
            driver.execute_script(script)
            sleep(2)
        except CaptchaUnsolvableError:
            driver.refresh()
            raise

    # pylint: disable=too-many-locals
    @backoff.on_exception(wait_gen=backoff.constant,
                        exception=CaptchaUnsolvableError,
                        max_tries=3)
    def resolve_awsawf(self, driver):
        """Resolve AWS WAF Captcha"""

        # Intercept background network traffic via log sniffing
        sleep(2)
        logs = [json.loads(lr["message"])["message"] for lr in driver.get_log("performance")]

        def log_filter(log_):
            return (
                # is an actual response
                log_["method"] == "Network.responseReceived"
                # and json
                and "json" in log_["params"]["response"]["mimeType"]
            )

        context = None
        iv = None
        for log in filter(log_filter, logs):
            request_id = log["params"]["requestId"]
            resp_url = log["params"]["response"]["url"]
            if "problem" in resp_url and "awswaf" in resp_url:
                response = driver.execute_cdp_cmd(
                    "Network.getResponseBody", {"requestId": request_id}
                )
                response_json = json.loads(response["body"])
                iv = response_json["state"]["iv"]
                context = response_json["state"]["payload"]
                sitekey = response_json["key"]
        if context is None or iv is None:
            raise CaptchaUnsolvableError("Unable to find captcha data in logs")

        sitekey = re.findall(
            r"apiKey: \"(.*?)\"", driver.page_source)[0]

        challenge = None
        challenge_matches = re.findall(r'src="([^"]*challenge\.js)"', driver.page_source)
        for match in challenge_matches:
            logger.debug('Challenge SRC Value: %s', match)
            challenge = match

        jsapi = None
        jsapi_matches = re.findall(r'src="([^"]*jsapi\.js)"', driver.page_source)
        for match in jsapi_matches:
            logger.debug('JsApi SRC Value: %s', match)
            jsapi = match

        if challenge is None or jsapi is None:
            raise CaptchaUnsolvableError("Unable to find challenge or JSApi value in page source")

        try:
            captcha = self.captcha_solver.solve_awswaf(
                sitekey,
                iv,
                context,
                challenge,
                jsapi,
                driver.current_url
            )
            old_cookie = driver.get_cookie('aws-waf-token')
            new_cookie = old_cookie
            new_cookie['value'] = captcha.token
            driver.delete_cookie('aws-waf-token')
            driver.add_cookie(new_cookie)
            sleep(1)
            driver.refresh()
        except CaptchaUnsolvableError:
            driver.refresh()
            raise

    @backoff.on_exception(wait_gen=backoff.constant,
                          exception=CaptchaUnsolvableError,
                          max_tries=3)
    def resolve_recaptcha(self, driver, checkbox: bool, afterlogin_string: str = ""):
        """Resolve Captcha"""
        iframe_present = self._wait_for_iframe(driver)
        if checkbox is False and afterlogin_string == "" and iframe_present:
            google_site_key = driver \
                .find_element_by_class_name("g-recaptcha") \
                .get_attribute("data-sitekey")

            try:
                captcha_result = self.captcha_solver.solve_recaptcha(
                    google_site_key,
                    driver.current_url
                ).result

                driver.execute_script(
                    f'document.getElementById("g-recaptcha-response").innerHTML="{captcha_result}";'
                )

                #  Below function call can be different depending on the websites
                #  implementation. It is responsible for sending the promise that we
                #  get from recaptcha_answer. For now, if it breaks, it is required to
                #  reverse engineer it by hand. Not sure if there is a way to automate it.
                driver.execute_script(f'solvedCaptcha("{captcha_result}")')
                self._wait_until_iframe_disappears(driver)
            except CaptchaUnsolvableError:
                driver.refresh()
                raise
        else:
            if checkbox:
                self._clickcaptcha(driver, checkbox)
            else:
                self._wait_for_captcha_resolution(
                    driver, checkbox, afterlogin_string)

    def _clickcaptcha(self, driver, checkbox: bool):
        driver.switch_to.frame(driver.find_element_by_tag_name("iframe"))
        recaptcha_checkbox = driver.find_element_by_class_name(
            "recaptcha-checkbox-checkmark")
        recaptcha_checkbox.click()
        self._wait_for_captcha_resolution(driver, checkbox)
        driver.switch_to.default_content()

    def _wait_for_captcha_resolution(self, driver, checkbox: bool, afterlogin_string=""):
        if checkbox:
            try:
                WebDriverWait(driver, 120).until(
                    EC.visibility_of_element_located(
                        (By.CLASS_NAME, "recaptcha-checkbox-checked"))
                )
            except TimeoutException:
                logger.warning(
                    "Selenium.Timeoutexception when waiting for captcha to appear")
        else:
            xpath_string = f"//*[contains(text(), '{afterlogin_string}')]"
            try:
                WebDriverWait(driver, 120) \
                    .until(EC.visibility_of_element_located((By.XPATH, xpath_string)))
            except TimeoutException:
                logger.warning(
                    "Selenium.Timeoutexception when waiting for captcha to disappear")

    def _wait_for_iframe(self, driver: Chrome):
        """Wait for iFrame to appear"""
        try:
            iframe = WebDriverWait(driver, 10).until(EC.visibility_of_element_located(
                (By.CSS_SELECTOR, "iframe[src^='https://www.google.com/recaptcha/api2/anchor?']")))
            return iframe
        except NoSuchElementException:
            logger.info(
                "No iframe found, therefore no chaptcha verification necessary")
            return None
        except TimeoutException:
            logger.info(
                "Timeout waiting for iframe element - no captcha verification necessary?")
            return None

    def _wait_until_iframe_disappears(self, driver: Chrome):
        """Wait for iFrame to disappear"""
        try:
            WebDriverWait(driver, 10).until(EC.invisibility_of_element(
                (By.CSS_SELECTOR, "iframe[src^='https://www.google.com/recaptcha/api2/anchor?']")))
        except NoSuchElementException:
            logger.warning("Element not found")
