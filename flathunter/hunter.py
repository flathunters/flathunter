"""Default Flathunter implementation for the command line"""
import traceback
from itertools import chain
import requests

from flathunter.logging import logger
from flathunter.config import YamlConfig
from flathunter.filter import Filter
from flathunter.processor import ProcessorChain
from flathunter.captcha.captcha_solver import CaptchaUnsolvableError
from flathunter.exceptions import ConfigException

class Hunter:
    """Basic methods for crawling and processing / filtering exposes"""

    def __init__(self, config: YamlConfig, id_watch):
        self.config = config
        if not isinstance(self.config, YamlConfig):
            raise ConfigException(
                "Invalid config for hunter - should be a 'Config' object")
        self.id_watch = id_watch

    def crawl_for_exposes(self, max_pages=None):
        """Trigger a new crawl of the configured URLs"""
        def try_crawl(searcher, url, max_pages):
            try:
                return searcher.crawl(url, max_pages)
            except CaptchaUnsolvableError:
                logger.info("Error while scraping url %s: the captcha was unsolvable", url)
                return []
            except requests.exceptions.RequestException:
                logger.info("Error while scraping url %s:\n%s", url, traceback.format_exc())
                return []

        return chain(*[try_crawl(searcher, url, max_pages)
                       for searcher in self.config.searchers()
                       for url in self.config.target_urls()])

    def hunt_flats(self, max_pages: None|int = None):
        """Crawl, process and filter exposes"""
        filter_set = Filter.builder() \
                           .read_config(self.config) \
                           .filter_already_seen(self.id_watch) \
                           .build()

        processor_chain = ProcessorChain.builder(self.config) \
                                        .save_all_exposes(self.id_watch) \
                                        .apply_filter(filter_set) \
                                        .resolve_addresses() \
                                        .calculate_durations() \
                                        .send_messages() \
                                        .build()

        result = []
        # We need to iterate over this list to force the evaluation of the pipeline
        for expose in processor_chain.process(self.crawl_for_exposes(max_pages)):
            logger.info('New offer: %s', expose['title'])
            result.append(expose)

        return result
