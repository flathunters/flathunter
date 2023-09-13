"""Calculate Google-Maps distances between specific locations and the target flat"""
import datetime
import time
from urllib.parse import quote_plus
from typing import Dict
import requests
from flathunter.dataclasses import DistanceElement, DistanceValueTuple, DurationValueTuple, TransportationModes

from flathunter.logging import logger
from flathunter.abstract_processor import Processor


class GMapsDurationProcessor(Processor):
    """Implementation of Processor class to calculate travel durations"""

    def __init__(self, config):
        self.config = config

    def process_expose(self, expose):
        """Calculate the durations for an expose"""
        durations = self.get_distances_and_durations(expose['address'])
        expose['durations'] = self._format_durations(durations).strip()
        expose['durations_unformatted'] = durations
        return expose

    def get_distances_and_durations(self, address) -> Dict[str, DistanceElement]:
        """Return a dict mapping location names to distances and durations"""
        out = {}
        for duration in self.config.get('durations', []):
            if 'destination' not in duration or 'name' not in duration or 'modes' not in duration:
                logger.warning('illegal duration configuration: %s', duration)
                continue
            dest = duration.get('destination')
            name = duration.get('name')
            for mode in duration.get('modes', []):
                if 'gm_id' in mode and 'title' in mode \
                                   and 'key' in self.config.get('google_maps_api', {}):
                    duration = self._get_gmaps_distance(address, dest, mode['gm_id'])
                    out[name] = duration
        return out

    def get_formatted_durations(self, address):
        """Return a formatted list of GoogleMaps durations"""
        durations = self.get_distances_and_durations(address)
        return self._format_durations(durations)

    def _format_durations(self, durations: Dict[str, DistanceElement]):
        out = ""
        for location_name, val in durations.items():
            out += f"> {location_name} ({val.mode.value}): {val.duration.text} ({val.distance.text})\n"
        return out.strip()

    def _get_gmaps_distance(self, address, dest, mode) -> DistanceElement | None:
        """Get the distance"""
        # get timestamp for next monday at 9:00:00 o'clock
        now = datetime.datetime.today().replace(hour=9, minute=0, second=0)
        next_monday = now + datetime.timedelta(days=7 - now.weekday())
        arrival_time = str(int(time.mktime(next_monday.timetuple())))

        # decode from unicode and url encode addresses
        address = quote_plus(address.strip().encode('utf8'))
        dest = quote_plus(dest.strip().encode('utf8'))
        logger.debug("Got address: %s", address)

        # get google maps config stuff
        base_url = self.config.get('google_maps_api', {}).get('url')
        gm_key = self.config.get('google_maps_api', {}).get('key')

        if not gm_key and mode != TransportationModes.DRIVING:
            logger.warning("No Google Maps API key configured and without using a mode "
                "different from 'driving' is not allowed. Thus downgrading to mode 'driving'.")
            mode = TransportationModes.DRIVING
            base_url = base_url.replace('&key={key}', '')

        # retrieve the result
        url = base_url.format(dest=dest, mode=mode, origin=address,
                              key=gm_key, arrival=arrival_time)
        result = requests.get(url, timeout=30).json()
        if result['status'] != 'OK':
            logger.error("Failed retrieving distance to address %s: %s", address, result)
            return None

        # get the fastest route
        distances = {}
        for row in result['rows']:
            for element in row['elements']:
                if 'status' in element and element['status'] != 'OK':
                    logger.warning("For address %s we got the status message: %s",
                                         address, element['status'])
                    logger.debug("We got this result: %s", repr(result))
                    continue
                logger.debug("Got distance and duration: %s / %s (%i seconds)",
                                   element['distance']['text'],
                                   element['duration']['text'],
                                   element['duration']['value'])
                distance_element = DistanceElement(
                    duration=DurationValueTuple(
                        float(element['duration']['value']),
                        element['duration']['text']),
                    distance=DistanceValueTuple(
                        float(element['distance']['value']),
                        element['distance']['text']),
                    mode=TransportationModes(mode)
                )
                distances[distance_element.distance.meters] = distance_element
        return distances[min(distances.keys())] if distances else None
