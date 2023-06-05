"""Storage back-end implementation using Google Cloud Firestore"""
import datetime
import pytz
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import BaseQuery

from flathunter.logging import logger
from flathunter.exceptions import PersistenceException


class GoogleCloudIdMaintainer:
    """Storage back-end - implementation of IdMaintainer API"""

    def __init__(self, config):
        project_id = config.google_cloud_project_id()
        if project_id is None:
            raise PersistenceException(
                "Need to project a google_cloud_project_id in config.yaml")
        firebase_admin.initialize_app(credentials.ApplicationDefault(), {
            'projectId': project_id
        })
        self.database = firestore.client()

    def mark_processed(self, expose_id):
        """Mark exposes as processed when we have processed them"""
        logger.debug('mark_processed(%d)', expose_id)
        self.database.collection('processed').document(
            str(expose_id)).set({'id': expose_id})

    def is_processed(self, expose_id):
        """Returns true if an expose has already been marked as processed"""
        logger.debug('is_processed(%d)', expose_id)
        doc = self.database.collection('processed').document(str(expose_id))
        return doc.get().exists

    def save_expose(self, expose):
        """Writes an expose to the storage backend"""
        record = expose.copy()
        record.update({'created_at': pytz.utc.localize(datetime.datetime.now()),
                       'created_sort': (0 - datetime.datetime.now().timestamp())})
        self.database.collection('exposes').document(
            str(expose['id'])).set(record)

    def get_exposes_since(self, min_datetime):
        """Returns all exposes since the supplied datetime"""
        localized_datetime = min_datetime.replace(tzinfo=pytz.UTC)
        res = []
        for doc in self.database.collection('exposes') \
                .order_by('created_sort').limit(10000).stream():
            if doc.to_dict()['created_at'] < localized_datetime:
                break
            res.append(doc.to_dict())
        return res

    def get_recent_exposes(self, count, filter_set=None):
        """Returns recent exposes (no more than 'count'), conforming to
           the provided filter if supplied"""
        res = []
        for doc in self.database.collection('exposes') \
                .order_by('created_sort').limit(100).stream():
            expose = doc.to_dict()
            if filter_set is None or filter_set.is_interesting_expose(expose):
                res.append(expose)
                if len(res) == count:
                    break
        return res

    def get_settings_for_user(self, user_id):
        """Loads the user settings from the database"""
        doc = self.database.collection('users').document(str(user_id)).get()
        return doc.to_dict()

    def save_settings_for_user(self, user_id, settings):
        """Saves the user settings to the database"""
        self.database.collection('users').document(str(user_id)).set(settings)

    def get_user_settings(self):
        """Loads all users' settings from the database"""
        res = []
        for doc in self.database.collection('users').stream():
            settings = doc.to_dict()
            if settings is not None:
                res.append((int(doc.id), settings))
        return res

    def get_last_run_time(self):
        """Returns the datetime of the last run"""

        docs = self.database.collection('executions').order_by(
            'timestamp', direction=BaseQuery.DESCENDING).limit(1).stream()
        for doc in docs:
            return doc.to_dict()['timestamp']

    def update_last_run_time(self):
        """Updates the time of the last run in the database"""
        time = datetime.datetime.now()
        self.database.collection('executions').add({'timestamp': time})
        return time
