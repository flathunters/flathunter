"""Functions and classes related to sending Telegram messages"""
import json
import time
from typing import List, Dict, Optional

import requests

from flathunter.abstract_notifier import Notifier
from flathunter.abstract_processor import Processor
from flathunter.config import YamlConfig
from flathunter.exceptions import BotBlockedException
from flathunter.exceptions import UserDeactivatedException
from flathunter.logging import logger
from flathunter.utils.list import chunk_list


class SenderTelegram(Processor, Notifier):
    """Expose processor that sends Telegram messages"""

    def __init__(self, config: YamlConfig, receivers=None):
        self.config = config
        self.bot_token = self.config.telegram_bot_token()
        self.__notify_with_images: bool = self.config.telegram_notify_with_images()

        self.__text_message_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        self.__media_group_url = f"https://api.telegram.org/bot{self.bot_token}/sendMediaGroup"

        if receivers is None:
            self.receiver_ids = self.config.telegram_receiver_ids()
        else:
            self.receiver_ids = receivers

    def process_expose(self, expose):
        """Send a message to a user describing the expose"""
        self.__broadcast(
            receivers=self.receiver_ids,
            message=self.__get_text_message(expose),
            images=self.__get_images(expose),
        )
        return expose

    def __broadcast(self,
                    receivers: List[int],
                    message: str,
                    images: Optional[List[str]] = None) -> None:
        """
        Broadcast given message to the given receiver ids
        :param receivers: list of user/group ids
        :param message: text message to send to users
        :param images: images to send to users as a reply to message
        :return: None
        """
        for receiver in receivers:
            msg = self.__send_text(receiver, message)
            if not msg:
                continue

            if self.__notify_with_images and images:
                self.__send_images(chat_id=receiver, msg=msg, images=images)

    def notify(self, message: str):
        """
        Send messages to each of the receivers in receiver_ids
        :param message: a message that should be sent to users
        :return: None
        """
        self.__broadcast(self.receiver_ids, message, None)

    def __send_text(self, chat_id: int, message: str) -> Dict:
        """
        Send bot text message, the message may contain a simple
        heartbeat message or an apartment information
        :param chat_id: the receiver id
        :param message: the body of the message
        :return: sent message information
        """

        payload = {
            'chat_id': str(chat_id),
            'text': message,
        }
        logger.debug(('token:', self.bot_token))
        logger.debug(('chat_id:', chat_id))
        logger.debug(('text:', message))
        logger.debug("Retrieving URL %s, payload %s", self.__text_message_url, payload)
        response = requests.request("POST", self.__text_message_url, data=payload, timeout=30)
        logger.debug("Got response (%i): %s", response.status_code, response.content)

        # handle error
        if response.status_code != 200:
            self.__handle_error("When sending bot text message, we got an error.",
                response, chat_id)
            return {}

        return response.json().get('result', {})

    def __send_images(self, chat_id: int, msg: Dict, images: List[str]):
        """
        Send image to given user id (receiver).
        If msg is not None, it will send the images as a response to given message
        :param chat_id: the user/group that will receive the image
        :param msg: message that will be replied to
        :param images: list of urls
        :return: None
        """
        # maximum number of images in a media group is 10.
        # if there are more than 10 images, we need to divide it into multiple messages.
        for chunk in chunk_list(images, 10):
            payload = {
                'chat_id': str(chat_id),
                # media expected to be an array of objects in string format
                'media': json.dumps([{"type": "photo", "media": url} for url in chunk]),
                'disable_notification': True,
            }
            if msg.get('message_id', None):
                payload['reply_to_message_id'] = msg.get('message_id')

            response = requests.request("POST", self.__media_group_url, data=payload, timeout=30)

            if response.status_code != 200:
                logger.warning("Error sending media group: %s", json.dumps(payload))
                self.__handle_error(
                    "When sending media group, we got an error.",
                    response=response,
                    chat_id=str(chat_id)
                )
                return

    def __handle_error(self, msg: str, response, chat_id) -> None:
        """
        Handles telegram API error responses
        :param msg: the message for logging
        :param response: the response that is received form the API
        :param chat_id: the receiver that was supposed to get the message
        :return: None

        :raise BotBlockedException: Happens when bot trys to send a message to a user that
            has already blocked the bot
        :raise UserDeactivatedException: Happens when bot try to send a message to a
            deactivated user
        """
        status_code = response.status_code
        data = response.json()

        logger.error("%s, status code: %i, data: %s" , msg, status_code, data)

        if response.status_code == 403:
            if "bot was blocked by the user" in data.get("description", ""):
                raise BotBlockedException(f"User {chat_id} blocked the bot")
            if "user is deactivated" in data.get("description", ""):
                raise UserDeactivatedException(f"User {chat_id} has been deactivated")
        if response.status_code == 429:
            if "Too Many Requests" in data.get("description", ""):
                backoff = data.get("parameters", {}).get("retry_after", 30)
                time.sleep(min(backoff, 30))
                return None
        return None

    def __get_images(self, expose: Dict) -> List[str]:
        return expose.get("images", [])

    def __get_text_message(self, expose: Dict) -> str:
        """
        Build text message based on the exposed data
        :param expose: dictionary
        :return: str
        """

        return self.config.message_format().format(
            title=expose.get('title', 'N/A'),
            rooms=expose.get('rooms', 'N/A'),
            size=expose.get('size', 'N/A'),
            price=expose.get('price', 'N/A'),
            url=expose.get('url', 'N/A'),
            address=expose.get('address', 'N/A'),
            durations=expose.get('durations', 'N/A'),
            application=expose.get('generated_text', 'N/A')
        ).strip()
