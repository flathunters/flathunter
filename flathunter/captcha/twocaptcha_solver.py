"""Captcha solver for 2Captcha Captcha Solving Service (https://2captcha.com)"""
import base64
import json
from io import BytesIO
from typing import Dict
from time import sleep

import backoff
import requests
from twocaptcha import TwoCaptcha

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

from flathunter.logging import logger
from flathunter.captcha.captcha_solver import (
    CaptchaSolver,
    CaptchaBalanceEmpty,
    CaptchaUnsolvableError,
    GeetestResponse,
    AwsAwfResponse,
    RecaptchaResponse,
)

class TwoCaptchaSolver(CaptchaSolver):
    """Implementation of Captcha solver for 2Captcha"""

    def solve_geetest(self, geetest: str, challenge: str, page_url: str) -> GeetestResponse:
        """Solves GeeTest Captcha"""
        logger.info("Trying to solve geetest.")
        params = {
            "key": self.api_key,
            "method": "geetest",
            "api_server": "api.geetest.com",
            "gt": geetest,
            "challenge": challenge,
            "pageurl": page_url
        }
        captcha_id = self.__submit_2captcha_request(params)
        untyped_result = json.loads(self.__retrieve_2captcha_result(captcha_id))
        return GeetestResponse(untyped_result["geetest_challenge"],
                               untyped_result["geetest_validate"],
                               untyped_result["geetest_seccode"])


    def solve_recaptcha(self, google_site_key: str, page_url: str) -> RecaptchaResponse:
        logger.info("Trying to solve recaptcha.")
        params = {
            "key": self.api_key,
            "method": "userrecaptcha",
            "googlekey": google_site_key,
            "pageurl": page_url
        }
        captcha_id = self.__submit_2captcha_request(params)
        return RecaptchaResponse(self.__retrieve_2captcha_result(captcha_id))

    def resolve_awswaf(self, driver):
        """Resolve Amazon Captcha"""
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            sleep(3)
            shadowelement = driver.execute_script(
                "return document.querySelector('awswaf-captcha').shadowRoot"
            )
            my_img = shadowelement.find_element(By.ID, "root")
            size = my_img.size
            select_l = my_img.find_element(By.TAG_NAME, "select")
            select_l.click()
            sleep(1)
            select_l.send_keys(Keys.DOWN)
            sleep(3)
            shadowelement = driver.execute_script(
                "return document.querySelector('awswaf-captcha').shadowRoot"
            )
            my_img = shadowelement.find_element(By.ID, "root")
            screenshot = my_img.screenshot_as_png
            screenshot_bytes = BytesIO(screenshot)
            base64_screenshot = base64.b64encode(screenshot_bytes.getvalue()).decode('utf-8')
            # Send image in 2captcha service
            result = self.solve_awswaf(base64_screenshot)
            logger.info(result.token)
            l = result.token.split(':')[1].split(';')
            l = [[int(val.split('=')[1]) for val in coord.split(',')] for coord in l]
            button_coord = [size['width'] - 30, size['height'] - 30]
            l.append(button_coord)
            actions = ActionChains(driver)
            for i in l:
                actions.move_to_element_with_offset(my_img, i[0] - 160, i[1] - 211).click()
                actions.perform()
                sleep(0.5)
                actions.reset_actions()
            sleep(1)
            try:
                confirm_button = my_img.find_element(By.ID, "amzn-btn-verify-internal")
                actions.move_to_element_with_offset(confirm_button, 40, 15).click()
                actions.perform()
                sleep(4)
            except NoSuchElementException:
                pass
            try:
                driver.find_element(By.TAG_NAME, "awswaf-captcha")
            except NoSuchElementException:
                logger.info("Captcha solved")
            else:
                raise CaptchaUnsolvableError()
        except Exception as ex:
            driver.refresh()
            raise CaptchaUnsolvableError() from ex

    def solve_awswaf(
        self,
        image_b64: str
    ) -> AwsAwfResponse:
        """Solve AWS WAF by processing an image"""
        solver = TwoCaptcha(self.api_key, defaultTimeout=60, pollingInterval=5)
        result = solver.coordinates(image_b64, lang='en')
        if result is None:
            raise CaptchaUnsolvableError("Got None from 2captcha solve")
        return AwsAwfResponse(result["code"])

    @backoff.on_exception(**CaptchaSolver.backoff_options)
    def __submit_2captcha_request(self, params: Dict[str, str]) -> str:
        submit_url = "http://2captcha.com/in.php"
        submit_response = requests.post(submit_url, params=params, timeout=30)
        logger.info("Got response from 2captcha/in: %s", submit_response.text)

        if not submit_response.text.startswith("OK"):
            raise requests.HTTPError(response=submit_response)

        return submit_response.text.split("|")[1]


    @backoff.on_exception(**CaptchaSolver.backoff_options)
    def __retrieve_2captcha_result(self, captcha_id: str):
        retrieve_url = "http://2captcha.com/res.php"
        params = {
            "key": self.api_key,
            "action": "get",
            "id": captcha_id,
            "json": 0,
        }
        while True:
            retrieve_response = requests.get(retrieve_url, params=params, timeout=30)
            logger.debug("Got response from 2captcha/res: %s", retrieve_response.text)

            if "CAPCHA_NOT_READY" in retrieve_response.text:
                logger.info("Captcha is not ready yet, waiting...")
                sleep(5)
                continue

            if "ERROR_CAPTCHA_UNSOLVABLE" in retrieve_response.text:
                logger.info("The captcha was unsolvable.")
                raise CaptchaUnsolvableError()

            if "ERROR_ZERO_BALANCE" in retrieve_response.text:
                logger.info("2captcha account out of credit - buy more captchas.")
                raise CaptchaBalanceEmpty()

            if not retrieve_response.text.startswith("OK"):
                raise requests.HTTPError(response=retrieve_response)

            return retrieve_response.text.split("|", 1)[1]
