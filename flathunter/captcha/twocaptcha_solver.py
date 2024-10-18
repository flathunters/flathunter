"""Captcha solver for 2Captcha Captcha Solving Service (https://2captcha.com)"""
import json
from typing import Dict
from time import sleep
import backoff
import requests

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

    def solve_awswaf(
        self,
        sitekey: str,
        iv: str,
        context: str,
        challenge_script: str,
        captcha_script: str,
        page_url: str
    ) -> AwsAwfResponse:
        """Should be implemented at some point"""
        raise NotImplementedError("AWS WAF captchas not supported for 2Captcha")

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
