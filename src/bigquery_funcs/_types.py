import datetime as dt
from collections.abc import Sequence
from typing import (
    Any,
    Callable,
    Iterable,
    Literal,
    NamedTuple,
    TypeAlias,
    TypedDict,
)

SecretContextType: TypeAlias = Literal["local", "google_secrets_manager"]
BigQueryFuncName: TypeAlias = str

OrderedPairs: TypeAlias = Sequence[
    Sequence[str] | Sequence[float] | Sequence[int] | Sequence[complex]
]


class LatLon(NamedTuple):
    lat: float
    lon: float


class LonLat(NamedTuple):
    lon: float
    lat: float


class MatchedCoord(TypedDict):
    given_coord: LatLon
    matched_coord: LatLon
    city_match: str
    state_match: str
    country_match: str


DateTimeFormatter: TypeAlias = Callable[[dt.datetime], str]

JsonRow: TypeAlias = dict[str, Any]
JsonRows: TypeAlias = Iterable[JsonRow]  # pyright: ignore[reportExplicitAny]
