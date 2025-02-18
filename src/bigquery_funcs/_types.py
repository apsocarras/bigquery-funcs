from typing import Literal, NamedTuple, TypeAlias, TypedDict

SecretContextType: TypeAlias = Literal["local", "google_secrets_manager"]
BigQueryFuncName: TypeAlias = str


class LatLon(NamedTuple):
    lat: float
    lon: float


class MatchedCoord(TypedDict):
    given_coord: LatLon
    matched_coord: LatLon
    city_match: str
    state_match: str
    country_match: str
