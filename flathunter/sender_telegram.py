"""Functions and classes related to sending Telegram messages"""
from flathunter.logging import logger
from flathunter.abstract_processor import Processor
from flathunter.sender_apprise import SenderApprise

class SenderTelegram(Processor):
    """Expose processor that sends Telegram messages"""

    def __init__(self, config, receivers=None):
        self.config = config
        self.bot_token = self.config.get('telegram', {}).get('bot_token', '')
        if receivers is None:
            self.receiver_ids = self.config.get('telegram', {}).get('receiver_ids', [])
        else:
            self.receiver_ids = receivers

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

    def send_msg(self, message):
        """Send messages to each of the receivers in receiver_ids"""
        if self.receiver_ids is None:
            return

        apprise_urls = []
        for chat_id in self.receiver_ids:
            apprise_urls.append(f"tgram://{self.bot_token}/{chat_id}")

        SenderApprise.send(message, apprise_urls)
        
