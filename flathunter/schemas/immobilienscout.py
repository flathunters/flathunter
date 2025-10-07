"""Schemas for Immobilienscout crawler"""
from typing import Any, ClassVar, Literal
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator
)

from flathunter.logging import logger

class ImmoscoutQuery(BaseModel):
    """Pydantic model to validate and transform an Immoscout search URL"""

    REAL_ESTATE_TYPE_MAP: ClassVar[dict] = {
        "haus-mieten": "houserent",
        "wohnung-mieten": "apartmentrent",
        "wohnung-kaufen": "apartmentbuy",
        "haus-kaufen": "housebuy"
    }

    REAL_ESTATE_TYPE_TO_APARTMENT_EQUIPMENT_MAP: ClassVar[dict] = {
        # Category "Balkon/Terrasse"
        "wohnung-mit-balkon-mieten": { "equipment": ["balcony"] },
        "wohnung-mit-garten-mieten": { "equipment": ["garden"] },
        # Category "Wohnungstyp"
        "souterrainwohnung-mieten": { "apartmenttypes": ["halfbasement"] },
        "erdgeschosswohnung-mieten": { "apartmenttypes": ["groundfloor"] },
        "hochparterrewohnung-mieten": { "apartmenttypes": ["raisedgroundfloor"] },
        "etagenwohnung-mieten": { "apartmenttypes": ["apartment"] },
        "loft-mieten": { "apartmenttypes": ["loft"] },
        "maisonette-mieten": { "apartmenttypes": ["maisonette"] },
        "terrassenwohnung-mieten": { "apartmenttypes": ["terracedflat"] },
        "penthouse-mieten": { "apartmenttypes": ["penthouse"] },
        "dachgeschosswohnung-mieten": { "apartmenttypes": ["roofstorey"] },
        # Category "Ausstattung"
        "wohnung-mit-garage-mieten": { "equipment": ["parking"] },
        "wohnung-mit-einbaukueche-mieten": { "equipment": ["builtinkitchen"] },
        "wohnung-mit-keller-mieten": { "equipment": ["cellar"] },
        # Category "Merkmale"
        "neubauwohnung-mieten": { "newbuilding": "true" },
        "barrierefreie-wohnung-mieten": { "equipment": ["handicappedaccessible"] }
    }

    SORTING_MAP: ClassVar[dict] = {
        "2": "-firstactivation", # newest offer first
        "3": "-price", # price descending
        "4": "price", # price ascending
        "5": "-rooms", # number of rooms descending
        "6": "rooms", # number of rooms ascending
        "7": "-livingspace", # living space descending
        "8": "livingspace" # living space ascending
    }

    model_config = ConfigDict(serialize_by_alias=True)

    apartmenttypes: list[str] | None = Field(title="Wohnungstyp", default=None)
    constructionyear: str | None = Field(title="Baujahr", default=None)
    energyefficiencyclasses: list[str] | None = Field(title="Energieeffizienzklasse", default=None)
    equipment: list[str] | None = Field(title="Ausstattung", default=None)
    exclusioncriteria: list[str] | None = Field(title="Objektart", default=None)
    floor: str | None = Field(title="Etage", default=None)
    geocodes: str | None = Field(
        description="Path following '/Suche/' up to second to last element", default=None
    )
    geocoordinates: str | None = Field(
        description="Geocoordinates for radius-based search", default=None
    )
    haspromotion: bool | None = Field(title="Wohnberechtigungsschein (WBS)", default=None)
    heatingtypes: list[str] | None = Field(title="Heizungsart", default=None)
    livingspace: str | None = Field(title="Wohnfläche in m²", default=None)
    minimuminternetspeed: int | None = Field(title="Internetgeschwindigkeit", default=None)
    newbuilding: bool | None = Field(title="Neubau", default=None)
    numberofrooms: str | None = Field(title="Zimmer", default=None)
    pagenumber: int = Field(title="Page number", default=1)
    pagesize: int = Field(description="Results per page", default=20)
    petsallowedtypes: list[str] | None = Field(title="Haustiere", default=None)
    price: str | None = Field(title="Kalt/Warmmiete in €", default=None)
    pricetype: Literal["calculatedtotalrent", "rentpermonth"] = Field(
        description="Warm or net rent", default="rentpermonth"
    )
    realestatetype: Literal["apartmentbuy", "apartmentrent", "housebuy", "houserent"] = Field(
        description="Real estate and contract type"
    )
    searchtype: Literal["region", "radius"] = Field(
        description="Radius or region based search", serialization_alias="searchType"
    )
    sorting: str = Field(
        description="Sorting type identifier, default means newest offer first",
        default="2",
        validate_default=True
    )

    @model_validator(mode="before")
    @classmethod
    def set_fields_based_on_real_estate_type(cls, data: Any) -> Any:
        """Derives API query parameters from real estate type"""
        real_estate_type = data.get("realestatetype")
        additional_params = cls.REAL_ESTATE_TYPE_TO_APARTMENT_EQUIPMENT_MAP.get(
            real_estate_type, {}
        )
        for k, v in additional_params.items():
            data[k] = data[k] + v if isinstance(data.get(k), list) else v
        return data

    @field_validator(
        "realestatetype",
        mode="before"
    )
    @classmethod
    def map_real_estate_type(cls, real_estate_type: str) -> str:
        """Maps real estate type from search URL to API URL"""
        try:
            return cls.REAL_ESTATE_TYPE_MAP[real_estate_type]
        except KeyError as e:
            logger.warning(
                "Unknown real estate and contract type %s, defaulting to rental apartment",
                str(e)
            )
            return "apartmentrent"

    @field_validator(
        "sorting",
        mode="after"
    )
    @classmethod
    def map_sorting_identifier(cls, sorting_id: int) -> str:
        """Maps sorting type ID to API parameter"""
        try:
            return cls.SORTING_MAP[sorting_id]
        except KeyError as e:
            logger.warning(
                "Unknown sorting identifier %s, defaulting to newest offers first", str(e)
            )
            return "-firstactivation"

    @field_serializer(
        "haspromotion",
        "newbuilding"
    )
    @classmethod
    def serialize_booleans(cls, value: bool) -> str:
        """Converts Python-type booleans to JSON equivalents"""
        return "true" if value else "false"
