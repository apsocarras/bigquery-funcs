from collections import namedtuple
from typing import Literal, TypeAlias, TypedDict

SecretContextType: TypeAlias = Literal["local", "google_secrets_manager"]
BigQueryFuncName: TypeAlias = str
LatLon = namedtuple("LatLon", ["lat", "lon"])


class MatchedCoord(TypedDict):
    given_coord: LatLon
    matched_coord: LatLon
    city_match: str
    state_match: str
    country_match: str
