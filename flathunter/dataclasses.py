"""
This module contains dataclasses to help with serialisation and typechecking of data
sent to and received from the Google Maps Distance API
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TransportationModes(Enum):
    """The transportation mode for Google Maps distance calculation."""
    TRANSIT = 'transit'
    BICYCLING = 'bicycling'
    DRIVING = 'driving'
    WALKING = 'walking'


@dataclass
class DistanceValueTuple:
    """We want to keep both the numeric value of a distance, and its string representation."""
    meters: float
    text: str


@dataclass
class DurationValueTuple:
    """We want to keep both the numeric value of a duration, and its string representation."""
    seconds: float
    text: str


@dataclass
class DistanceElement:
    """Represents the distance from a property to some location."""
    duration: DurationValueTuple
    distance: DistanceValueTuple
    mode: TransportationModes


@dataclass
class DistanceConfig:
    """Represents distance filter information in the configuration file.
    
    location_name must refer to the location name used to identify the location
    in the durations section of the config file, and the transport_mode must be
    configured in the durations section for that location name, lest no information
    is available to actually filter on."""
    location_name: str
    transport_mode: TransportationModes
    max_distance_meters: Optional[float]
    max_duration_seconds: Optional[float]


class FilterChainName(Enum):
    """Identifies the filter chain that a filter acts on
    
    Preprocess filters will be run before the expose is processed by any further actions.
    Use this chain to filter exposes that can be excluded based on information scraped 
    from the expose website alone (such as based on price or size).
    Postprocess filters will be run after other actions have completed. Use this if you
    require additional information from other steps, such as information from the Google
    Maps API, to make a decision on this expose.
    
    We separate the filter chains to avoid making expensive (literally!) calls to the
    Google Maps API for exposes that we already know we aren't interested in anyway."""
    PREPROCESS = 'PREPROCESS'
    POSTPROCESS = 'POSTPROCESS'
