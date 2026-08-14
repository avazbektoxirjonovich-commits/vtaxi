"""See docs/03-DATABASE-DESIGN.md SS2.2, table `administrative_areas`."""

from enum import StrEnum


class AdministrativeAreaLevel(StrEnum):
    """Arbitrary depth is supported by the self-referential table design;
    this list simply names the levels currently in use.
    """

    COUNTRY = "COUNTRY"
    REGION = "REGION"
    DISTRICT = "DISTRICT"
    CITY = "CITY"
    TOWN = "TOWN"
    VILLAGE = "VILLAGE"
    MAHALLA = "MAHALLA"
    STREET = "STREET"
