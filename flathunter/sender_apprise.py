"""Functions and classes related to sending Apprise messages"""
import apprise

from flathunter.exceptions import NotificationException
from flathunter.abstract_processor import Processor

class SenderApprise(Processor):
    """Expose processor that sends Apprise messages"""

    def __init__(self, config):
        self.config = config
        self.apprise_urls = self.config.get('apprise', {})

    def process_expose(self, expose):
        """Send a message to a user describing the expose"""
        message = self.config.get('message', "").format(
            title=expose['title'],
            rooms=expose['rooms'],
            size=expose['size'],
            price=expose['price'],
            url=expose['url'],
            address=expose['address'],
            durations="" if 'durations' not in expose else expose['durations']).strip()
        self.send_msg(message)
        return expose

    @staticmethod
    def send(message, apprise_urls):
        """Send messages using Apprise to a collection of URLs"""
        if apprise_urls is None or len(apprise_urls) == 0:
            return

        apobj = apprise.Apprise()

        for apprise_url in apprise_urls:
            apobj.add(apprise_url)

        all_successful = apobj.notify(
            body=message,
            title='',
            body_format=apprise.NotifyFormat.TEXT,
        )

        if not all_successful:
            raise NotificationException("Unable to send all the notifications")


    def send_msg(self, message):
        """Send messages to each of the Apprise URLs"""
        SenderApprise.send(message, self.apprise_urls)

        
