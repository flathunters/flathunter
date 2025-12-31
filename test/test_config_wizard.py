import pytest
import unittest
from unittest.mock import patch

from prompt_toolkit.document import Document
from prompt_toolkit.validation import ValidationError

from flathunter.config import YamlConfig
import config_wizard
from config_wizard import ConfigurationAborted, UrlsValidator, Notifier

class ConfigWizardTest(unittest.TestCase):

    def setUp(self):
        self.config = YamlConfig()
        self.config.init_searchers()

    @patch("config_wizard.prompt")
    def test_configure_telegram_throws_error_with_no_input(self, prompt_mock):
        prompt_mock.side_effect = [
            "",
            ""
        ]
        with pytest.raises(ConfigurationAborted):
            config_wizard.configure_telegram(self.config)

    @patch("config_wizard.prompt")
    def test_configure_telegram(self, prompt_mock):
        prompt_mock.side_effect = [
            "123",
            "456"
        ]
        res = config_wizard.configure_telegram(self.config)
        self.assertEqual(res["telegram"]["bot_token"], "123")
        self.assertEqual(res["telegram"]["receiver_ids"][0], 456)

    @patch("config_wizard.prompt")
    def test_configure_mattermost(self, prompt_mock):
        prompt_mock.side_effect = [
            "https://webhook.url"
        ]
        res = config_wizard.configure_mattermost(self.config)
        self.assertEqual(res["mattermost"]["webhook_url"], "https://webhook.url")

    @patch("config_wizard.prompt")
    def test_configure_mattermost_throws_exception_with_no_input(self, prompt_mock):
        prompt_mock.side_effect = [
            ""
        ]
        with pytest.raises(ConfigurationAborted):
            config_wizard.configure_mattermost(self.config)

    @patch("config_wizard.prompt")
    def test_configure_slack(self, prompt_mock):
        prompt_mock.side_effect = ["https://hooks.slack.url"]
        res = config_wizard.configure_slack(self.config)
        self.assertEqual(res["slack"]["webhook_url"], "https://hooks.slack.url")

    @patch("config_wizard.prompt")
    def test_configure_slack_throws_exception_with_no_input(self, prompt_mock):
        prompt_mock.side_effect = [""]
        with pytest.raises(ConfigurationAborted):
            config_wizard.configure_slack(self.config)

    @patch("config_wizard.prompt")
    def test_configure_apprise(self, prompt_mock):
        prompt_mock.side_effect = [
            "mailto://someone.who@cares.com"
        ]
        res = config_wizard.configure_apprise(self.config)
        self.assertEqual(res["apprise"][0], "mailto://someone.who@cares.com")

    @patch("config_wizard.prompt")
    def test_configure_apprise_throws_exception_with_no_input(self, prompt_mock):
        prompt_mock.side_effect = [
            ""
        ]
        with pytest.raises(ConfigurationAborted):
            config_wizard.configure_apprise(self.config)

    @patch("config_wizard.prompt")
    def test_gather_urls(self, prompt_mock):
        prompt_mock.side_effect = [
            "http://fish.com",
            ""
        ]
        urls = config_wizard.gather_urls(self.config)
        self.assertEqual(len(urls), 1)
        self.assertEqual("http://fish.com", urls[0])

    @patch("config_wizard.prompt")
    def test_configure_notifier(self, prompt_mock):
        prompt_mock.side_effect = [
            "", "", "", ""
        ]
        for notifier in Notifier:
            with pytest.raises(ConfigurationAborted):
                config_wizard.configure_notifier(notifier.value, self.config)

    @patch("config_wizard.prompt")
    def test_configure_captcha(self, prompt_mock):
        prompt_mock.side_effect = [
            "12345"
        ]
        urls = [
            "https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten?sorting=2"
        ]
        res = config_wizard.configure_captcha(urls, self.config)
        self.assertEqual((res or {}).get("captcha", {}).get("capmonster", {}).get("api_key"), "12345")

    def test_configure_captcha_is_none(self):
        urls = [
            "https://www.wg-gesucht.de/wohnungen-in-Berlin.8.2.1.0.html"
        ]
        self.assertIsNone(config_wizard.configure_captcha(urls, self.config))

    def test_urls_validator_raises_exception_for_invalid_url(self):
        doc = Document("https://www.url.com")
        validator = UrlsValidator([], self.config)
        with pytest.raises(ValidationError):
            validator.validate(doc)

    def test_urls_validator_passes(self):
        doc = Document("https://www.wg-gesucht.de/wohnungen-in-Berlin.8.2.1.0.html")
        validator = UrlsValidator([], self.config)
        self.assertFalse(validator.validate(doc))
