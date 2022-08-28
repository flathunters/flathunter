"""Flathunter implementation for website"""
from flathunter.logging import logger
from flathunter.hunter import Hunter
from flathunter.filter import Filter
from flathunter.processor import ProcessorChain
from flathunter.exceptions import NotificationException

class WebHunter(Hunter):
    """Flathunter implementation for website. Designed to hunt all exposes from
       all sites and save them to the database. Includes support for multiple users
       with individual filters implemented in-app"""

    def hunt_flats(self, max_pages=1):
        """Crawl all URLs, and send notifications to users of new flats"""
        filter_set = Filter.builder() \
                       .read_config(self.config) \
                       .filter_already_seen(self.id_watch) \
                       .build()

        processor_chain = ProcessorChain.builder(self.config) \
                                        .apply_filter(filter_set) \
                                        .crawl_expose_details() \
                                        .save_all_exposes(self.id_watch) \
                                        .resolve_addresses() \
                                        .calculate_durations() \
                                        .send_messages() \
                                        .build()

        new_exposes = []
        for expose in processor_chain.process(self.crawl_for_exposes(max_pages=max_pages)):
            new_exposes.append(expose)

        for (user_id, settings) in self.id_watch.get_user_settings():
            if 'mute_notifications' in settings:
                continue
            filter_set = Filter.builder().read_config(settings).build()
            try:
                processor_chain = ProcessorChain.builder(self.config) \
                                                .apply_filter(filter_set) \
                                                .send_messages([user_id]) \
                                                .build()
                for message in processor_chain.process(new_exposes):
                    logger.debug("Sent expose %d to user %d", message['id'], user_id)
            except NotificationException:
                logger.warn("Unable to send all notifications to %d - updating settings", user_id)
                settings["mute_notifications"] = True
                self.id_watch.save_settings_for_user(user_id, settings)


        self.id_watch.update_last_run_time()
        return list(new_exposes)

    def get_last_run_time(self):
        """Return the time of last run, for display on the website"""
        return self.id_watch.get_last_run_time()

    def get_recent_exposes(self, count=9, filter_set=None):
        """Load the most recent exposes matching the current filter"""
        return self.id_watch.get_recent_exposes(count, filter_set=filter_set)

    def get_exposes_since(self, min_datetime):
        """Return exposes since the provided datetime"""
        return self.id_watch.get_exposes_since(min_datetime)

    def set_filters_for_user(self, user_id, filters):
        """Set the filters for a given user"""
        settings = self.id_watch.get_settings_for_user(user_id)
        if settings is None:
            settings = {}
        settings['filters'] = filters
        self.id_watch.save_settings_for_user(user_id, settings)

    def get_filters_for_user(self, user_id):
        """Return the filters for a given user"""
        settings = self.id_watch.get_settings_for_user(user_id)
        if settings is None:
            return None
        if 'filters' in settings:
            return settings['filters']
        return None

    def set_notification_status(self, user_id, receives_notifications):
        """Enable or disable notifications for a user"""
        settings = self.id_watch.get_settings_for_user(user_id)
        if settings is None:
            if receives_notifications:
                return
            settings = {}
        if 'mute_notifications' in settings and receives_notifications:
            del settings['mute_notifications']
        if 'mute_notifications' not in settings and not receives_notifications:
            settings['mute_notifications'] = True
        self.id_watch.save_settings_for_user(user_id, settings)

    def toggle_notification_status(self, user_id):
        """Toggle notification status for the given user"""
        notifications_enabled = not self.notifications_muted_for_user(user_id)
        self.set_notification_status(user_id, not notifications_enabled)
        return not notifications_enabled

    def notifications_muted_for_user(self, user_id):
        """Returns true if the user has muted notifications"""
        settings = self.id_watch.get_settings_for_user(user_id)
        if settings is None:
            return False
        return 'mute_notifications' in settings
