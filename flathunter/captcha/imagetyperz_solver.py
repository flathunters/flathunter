"""Captcha solver using ImageTyperz Captcha Solving Service (http://www.imagetyperz.com)"""

import json
from typing import Dict
from time import sleep
import backoff
import requests

from flathunter.logging import logger
from flathunter.captcha.captcha_solver import (
    CaptchaSolver,
    CaptchaUnsolvableError,
    GeetestResponse,
    AwsAwfResponse,
    RecaptchaResponse,
)

class ImageTyperzSolver(CaptchaSolver):
    """Implementation of Captcha solver for ImageTyperz"""

    def solve_geetest(self, geetest: str, challenge: str, page_url: str) -> GeetestResponse:
        logger.info("Trying to solve geetest.")
        params = {
            "action": "UPLOADCAPTCHA",
            "domain": page_url,
            "challenge": challenge,
            "gt": geetest,
            "token": self.api_key,
        }
        captcha_id = self.__submit_imagetyperz_request(
            "http://www.captchatypers.com/captchaapi/UploadGeeTestToken.ashx",
            params
        )
        result = self.__retrieve_imagetyperz_result(captcha_id)

        # ImageTyperz sometimes returns a json object, and sometimes a ';;;;'-seperated list
        # one can only assume that the empolyees type in the webserver response by hand
        try:
            untyped_result = json.loads(result)
            return GeetestResponse(untyped_result["geetest_challenge"],
                                   untyped_result["geetest_validate"],
                                   untyped_result["geetest_seccode"])
        except json.decoder.JSONDecodeError:
            parts = result.split(";;;")
            return GeetestResponse(parts[0], parts[1], parts[2])


    def solve_recaptcha(self, google_site_key: str, page_url: str) -> RecaptchaResponse:
        logger.info("Trying to solve recaptcha.")
        params = {
            "action": "UPLOADCAPTCHA",
            "pageurl": page_url,
            "googlekey": google_site_key,
            "token": self.api_key,
        }
        captcha_id = self.__submit_imagetyperz_request(
            "http://www.captchatypers.com/captchaapi/UploadRecaptchaToken.ashx",
             params
        )
        return RecaptchaResponse(self.__retrieve_imagetyperz_result(captcha_id))

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
        raise NotImplementedError("AWS WAF captchas not supported for Imagetyperz")

    @backoff.on_exception(**CaptchaSolver.backoff_options)
    def __submit_imagetyperz_request(self, submit_url: str, params: Dict[str, str]) -> str:
        submit_response = requests.get(submit_url, params=params, timeout=30)
        logger.debug("Got response from imagetyperz/request: %s:", submit_response.text)

        if "error" in submit_response.text.lower():
            raise requests.HTTPError(response=submit_response)


        return submit_response.text


    @backoff.on_exception(**CaptchaSolver.backoff_options)
    def __retrieve_imagetyperz_result(self, captcha_id: str):
        retrieve_url = (
            "http://www.captchatypers.com/captchaapi/GetCaptchaResponseJson.ashx"
        )
        params = {
            "action": "GETTEXT",
            "token": self.api_key,
            "captchaid": captcha_id,
        }

        while True:
            retrieve_response = requests.get(retrieve_url, params=params, timeout=30)
            logger.debug("Got response from imagetyperz: %s:", retrieve_response.text)
            response = json.loads(retrieve_response.text)[0]
            if response["Status"] == "Pending":
                logger.info("Captcha is not ready yet, waiting...")
                sleep(5)
                continue

            if response["Status"] == "ERROR: IMAGE_TIMED_OUT":
                raise CaptchaUnsolvableError()
            if not response["Status"] == "Solved":
                raise requests.HTTPError(response=retrieve_response)

            return response["Response"]
