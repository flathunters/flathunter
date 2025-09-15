"""Captcha solver for CapMonster Captcha Solving Service (https://capmonster.cloud)"""
import json
import re
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
from flathunter.captcha.captcha_solver import CaptchaUnsolvableError

class CapmonsterSolver(CaptchaSolver):
    """Implementation of Captcha solver for CapMonster"""

    def solve_geetest(self, geetest: str, challenge: str, page_url: str) -> GeetestResponse:
        """Should be implemented in subclass"""
        raise NotImplementedError("Geetest captcha solving is not implemented for CapMonster")

    def solve_recaptcha(self, google_site_key: str, page_url: str) -> RecaptchaResponse:
        """Should be implemented in subclass"""
        raise NotImplementedError("Recaptcha captcha solving is not implemented for Capmonster")

    # pylint: disable=too-many-locals
    def resolve_awswaf(self, driver):
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

        for log in filter(log_filter, logs):
            request_id = log["params"]["requestId"]
            resp_url = log["params"]["response"]["url"]
            if "problem" in resp_url and "awswaf" in resp_url:
                response = driver.execute_cdp_cmd(
                    "Network.getResponseBody", {"requestId": request_id}
                )
                response_json = json.loads(response["body"])
                sitekey = response_json["key"]

        sitekey = re.findall(
            r"apiKey: \"(.*?)\"", driver.page_source)[0]

        jsapi = None
        jsapi_matches = re.findall(r'src="([^"]*jsapi\.js)"', driver.page_source)
        for match in jsapi_matches:
            logger.debug('JsApi SRC Value: %s', match)
            jsapi = match

        if jsapi is None:
            raise CaptchaUnsolvableError("Unable to find challenge or JSApi value in page source")

        try:
            captcha = self.solve_awswaf(
                sitekey,
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

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    def solve_awswaf(
        self,
        sitekey: str,
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
                raise requests.HTTPError(response=response_json["errorCode"])

            if response_json["status"] == "processing":
                logger.info("Captcha is not ready yet, waiting...")
                sleep(5)
                continue
            if response_json["status"] == "ready":
                return response_json["solution"]["cookies"]["aws-waf-token"]
