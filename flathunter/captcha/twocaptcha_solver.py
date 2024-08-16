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
    
    
    def solve_awswaf(self, sitekey: str, iv: str, context: str, challenge_script: str, captcha_script: str, page_url: str) -> AwsAwfResponse:
        """Solves AWS WAF Captcha"""
        logger.info("Trying to solve AWS WAF.")
        params = {
            "clientKey": "bafad5d1c0f567b8f2f4312c02340ba2",
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
            "clientKey": "bafad5d1c0f567b8f2f4312c02340ba2",
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