"""Captcha solver for CapMonster Captcha Solving Service (https://capmonster.cloud)"""
from typing import Dict
from time import sleep
import backoff
import requests

from flathunter.logging import logger
from flathunter.captcha.captcha_solver import (
    CaptchaSolver,
    GeetestResponse,
    AwsAwfResponse,
    RecaptchaResponse,
)

class CapmonsterSolver(CaptchaSolver):
    """Implementation of Captcha solver for CapMonster"""

    def solve_geetest(self, geetest: str, challenge: str, page_url: str) -> GeetestResponse:
        """Should be implemented in subclass"""
        raise NotImplementedError("Geetest captcha solving is not implemented for CapMonster")

    def solve_recaptcha(self, google_site_key: str, page_url: str) -> RecaptchaResponse:
        """Should be implemented in subclass"""
        raise NotImplementedError("Recaptcha captcha solving is not implemented for Capmonster")

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    def solve_awswaf(
        self,
        sitekey: str,
        iv: str,
        context: str,
        challenge_script: str,
        captcha_script: str,
        page_url: str
    ) -> AwsAwfResponse:
        """Solves AWS WAF Captcha"""
        logger.info("Trying to solve AWS WAF.")
        params = {
            "clientKey": self.api_key,
            "task": {
                "type": "AmazonTaskProxyless",
                "websiteURL": page_url,
                "challengeScript": "",
                "captchaScript": captcha_script,
                "websiteKey": sitekey,
                "context": "",
                "iv": "",
                "cookieSolution": True
            }
        }
        captcha_id = self.__submit_capmonster_request(params)
        untyped_result = self.__retrieve_capmonster_result(captcha_id)
        return AwsAwfResponse(untyped_result)

    @backoff.on_exception(**CaptchaSolver.backoff_options)
    def __submit_capmonster_request(self, params: Dict[str, str]) -> str:
        submit_url = "https://api.capmonster.cloud/createTask"
        submit_response = requests.post(submit_url, json=params, timeout=30)
        logger.info("Got response from capmonster: %s", submit_response.text)

        response_json = submit_response.json()

        return response_json["taskId"]

    @backoff.on_exception(**CaptchaSolver.backoff_options)
    def __retrieve_capmonster_result(self, captcha_id: str):
        retrieve_url = "https://api.capmonster.cloud/getTaskResult"
        params = {
            "clientKey": self.api_key,
            "taskId": captcha_id
        }
        while True:
            retrieve_response = requests.get(retrieve_url, json=params, timeout=30)
            logger.debug("Got response from capmonster: %s", retrieve_response.text)

            response_json = retrieve_response.json()
            if not "status" in response_json:
                raise requests.HTTPError(response=response_json["errrorCode"])

            if response_json["status"] == "processing":
                logger.info("Captcha is not ready yet, waiting...")
                sleep(5)
                continue
            if response_json["status"] == "ready":
                return response_json["solution"]["cookies"]["aws-waf-token"]
