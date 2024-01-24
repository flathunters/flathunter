#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Flathunter - search for flats by crawling property portals, and receive telegram
   messages about them. This is the main command-line executable, for running on the
   console. To run as a webservice, look at main.py"""

import time
from datetime import time as dtime

from flathunter.argument_parser import parse
from flathunter.logging import logger, configure_logging
from flathunter.idmaintainer import IdMaintainer
from flathunter.detailed_hunter import OpenAIHunter
from flathunter.config import Config
from flathunter.heartbeat import Heartbeat
from flathunter.time_utils import wait_during_period

__author__ = "Jan Harrie"
__version__ = "1.0"
__maintainer__ = "Nody"
__email__ = "harrymcfly@protonmail.com"
__status__ = "Production"


def launch_flat_hunt(config, heartbeat: Heartbeat):
    """Starts the crawler / notification loop"""
    id_watch = IdMaintainer(f'{config.database_location()}/processed_ids.db')

    time_from = dtime.fromisoformat(config.loop_pause_from())
    time_till = dtime.fromisoformat(config.loop_pause_till())

    wait_during_period(time_from, time_till)

    hunter = OpenAIHunter(config, id_watch)
    hunter.hunt_flats()
    counter = 0

    while config.loop_is_active():
        wait_during_period(time_from, time_till)

        counter += 1
        counter = heartbeat.send_heartbeat(counter)
        time.sleep(config.loop_period_seconds())
        hunter.hunt_flats()


def main():
    """Processes command-line arguments, loads the config, launches the flathunter"""
    # load config
    args = parse()
    config_handle = args.config
    if config_handle is not None:
        config = Config(config_handle.name)
    else:
        config = Config()

    # setup logging
    configure_logging(config)

    # initialize search plugins for config
    config.init_searchers()

    # check config
    notifiers = config.notifiers()
    if 'mattermost' in notifiers \
            and not config.mattermost_webhook_url():
        logger.error("No Mattermost webhook configured. Starting like this would be pointless...")
        return
    if 'telegram' in notifiers:
        if not config.telegram_bot_token():
            logger.error(
                "No Telegram bot token configured. Starting like this would be pointless..."
            )
            return
        if len(config.telegram_receiver_ids()) == 0:
            logger.warning("No Telegram receivers configured - nobody will get notifications.")
    if 'apprise' in notifiers \
            and not config.get('apprise', {}):
        logger.error("No apprise url configured. Starting like this would be pointless...")
        return
    if 'slack' in notifiers \
            and not config.slack_webhook_url():
        logger.error("No Slack webhook url configured. Starting like this would be pointless...")
        return

    if len(config.target_urls()) == 0:
        logger.error("No URLs configured. Starting like this would be pointless...")
        return

    # get heartbeat instructions
    heartbeat_interval = args.heartbeat
    heartbeat = Heartbeat(config, heartbeat_interval)

    # start hunting for flats
    launch_flat_hunt(config, heartbeat)


if __name__ == "__main__":
    main()
