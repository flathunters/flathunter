"""Default Flathunter implementation for the command line"""
import traceback
from itertools import chain
import requests

from flathunter.logging import logger
from flathunter.config import YamlConfig
from flathunter.filter import FilterChain
from flathunter.processor import ProcessorChain
from flathunter.captcha.captcha_solver import CaptchaUnsolvableError
from flathunter.exceptions import ConfigException
from flathunter.dataclasses import FilterChainName

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

    def hunt_flats(self, max_pages=None):
        """Crawl, process and filter exposes"""
        preprocess_filter_chain = self._build_preprocess_filter_chain(self.config)
        postprocess_filter_chain = self._build_postprocess_filter_chain(self.config)
        processor_chain = ProcessorChain.builder(self.config) \
                                        .save_all_exposes(self.id_watch) \
                                        .apply_filter(preprocess_filter_chain) \
                                        .resolve_addresses() \
                                        .calculate_durations() \
                                        .apply_filter(postprocess_filter_chain) \
                                        .send_messages() \
                                        .build()

        result = []
        # We need to iterate over this list to force the evaluation of the pipeline
        for expose in processor_chain.process(self.crawl_for_exposes(max_pages)):
            logger.info('New offer: %s', expose['title'])
            result.append(expose)

        return result
    
    def _build_preprocess_filter_chain(self, config) -> FilterChain:
        return FilterChain.builder() \
            .read_config(config, FilterChainName.preprocess) \
            .filter_already_seen(self.id_watch) \
            .build()
    
    def _build_postprocess_filter_chain(self, config) -> FilterChain:
        return FilterChain.builder() \
            .read_config(config, FilterChainName.postprocess) \
            .build()
