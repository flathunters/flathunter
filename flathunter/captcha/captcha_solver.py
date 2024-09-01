"""Interface for captcha solvers, among relevant data classes and exceptions.
Captcha solver implementations should subclass this."""

from dataclasses import dataclass
import requests
import backoff

@dataclass
class GeetestResponse:
    """Responde from GeeTest Captcha"""
    challenge: str
    validate: str
    sec_code: str

@dataclass
class RecaptchaResponse:
    """Response from reCAPTCHA"""
    result: str

class CaptchaSolver:
    """Interface for Captcha solvers"""

    backoff_options = {
        "wait_gen": backoff.constant,
        "exception": requests.exceptions.RequestException,
        "max_time": 100
    }

    def __init__(self, api_key):
        self.api_key = api_key

    def solve_geetest(self, geetest: str, challenge: str, page_url: str) -> GeetestResponse:
        """Should be implemented in subclass"""
        raise NotImplementedError()

    def solve_recaptcha(self, google_site_key: str, page_url: str) -> RecaptchaResponse:
        """Should be implemented in subclass"""
        raise NotImplementedError()

    def solve_amazon(self, image):
        raise NotImplementedError()

class CaptchaUnsolvableError(Exception):
    """Raised when Captcha was unsolveable"""
    def __init__(self):
        super().__init__()
        self.message = "Failed to solve captcha."

class CaptchaBalanceEmpty(Exception):
    """Raised when Captcha account is out of credit"""
    def __init__(self):
        super().__init__()
        self.message = "Captcha account balance empty."
