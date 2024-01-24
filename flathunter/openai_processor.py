"""Generate a text for an exposé with the help of OpenAI's API"""
import datetime
import time
from urllib.parse import quote_plus
import requests
from openai import OpenAI

from flathunter.logging import logger
from flathunter.abstract_processor import Processor

class OpenAIProcessor(Processor):
    """Implementation of Processor class to calculate travel durations"""


    def __init__(self, config):
        self.config = config
        self.client = OpenAI(api_key=self.config.openai_api_key())
        self.language = self.config.openai_language()

    def process_expose(self, expose):
        """Calculate the durations for an exposé"""
        expose['generated_text'] = self.generate_query_text(expose['rooms'], expose['description'], expose['lessor']).strip()
        return expose

    def generate_query_text(self, rooms, description, lessor) -> str:
        """Generate a text for an exposé with the help of OpenAI's API"""
        response = self.__openai_request(rooms, description, lessor)
        return response

    def __openai_request(self, room_count, description, lessor) -> str:
        """Send a request to OpenAI's API"""
        chat_completion = self.client.chat.completions.create(
            messages = [
                {
                    "role": "system",
                    "content": f"You are helping in generating an application for an exposé. For this, you will be provided with a dictionary which contains information on the kind of flat you are applying for and a prewritten text. The application is supposed to be written in {self.language}. Fill in the blanks, marked by [] in the text with the information from the dictionary. Do not directly copy text (except room information or similar things) from the dictionary - instead, paraphrase it."
                },
                {
                    "role": "user",
                    "content": f"Template:\n\n{self.config.openai_template()}"
                },
                {
                    "role": "user",
                    "content": f"Dictionary:\n\nrooms: {room_count},\nlessor to write to:{lessor},\ndescription: {description}"
                }
            ],
            model="gpt-3.5-turbo"
        )
        logger.info("Requested text generation from OpenAI API successfully")
        logger.debug("Exposé: %s", description)
        logger.debug("OpenAI response: %s", chat_completion)
        return chat_completion.choices[0].message.content
