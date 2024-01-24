"""Flathunter implementation for detailed exposé with OpenAI text generation."""
from flathunter.config import YamlConfig
from flathunter.logging import logger
from flathunter.hunter import Hunter
from flathunter.filter import Filter
from flathunter.processor import ProcessorChain
from flathunter.exceptions import BotBlockedException, UserDeactivatedException

class OpenAIHunter(Hunter):
    """Flathunter implementation for detailed exposé with OpenAI text generation"""


    def hunt_flats(self, max_pages=None):
        """Crawl, process and filter exposes"""
        filter_set = Filter.builder() \
                           .read_config(self.config) \
                           .filter_already_seen(self.id_watch) \
                           .build()

        processor_chain = ProcessorChain.builder(self.config) \
                                        .save_all_exposes(self.id_watch) \
                                        .apply_filter(filter_set) \
                                        .crawl_expose_details() \
                                        .resolve_addresses() \
                                        .calculate_durations() \
                                        .generate_text() \
                                        .send_messages() \
                                        .build()

        result = []
        # We need to iterate over this list to force the evaluation of the pipeline
        for expose in processor_chain.process(self.crawl_for_exposes(max_pages)):
            logger.info('New offer: %s', expose['title'])
            result.append(expose)

        return result
