import pytest
from faker import Faker
from faker.proxy import Faker

from bigquery_funcs._types import LatLon
from bigquery_funcs.queries import structify

from .utils import is_valid_query


@pytest.fixture
def known_lat_lons() -> tuple[LatLon, ...]:
    ## Test with a known set
    return tuple(
        (
            LatLon(2, 4),
            LatLon(1, 3),
        )
    )


@pytest.fixture
def rand_lat_lons() -> tuple[LatLon, ...]:
    fake = Faker()
    coords = tuple(
        LatLon(lat=float(lat), lon=float(lon))
        for lat, lon in (fake.location_on_land(coords_only=True) for _ in range(10))
    )
    return coords


def test_structify(
    rand_lat_lons: tuple[LatLon, ...], known_lat_lons: tuple[LatLon, ...]
) -> None:
    ## Test with a known set
    aliases = ("hello", "world")
    struct_tuple1 = structify(data=known_lat_lons, aliases=aliases)
    assert struct_tuple1 == (
        "STRUCT(2 AS hello, 4 AS world)",
        "STRUCT(1 AS hello, 3 AS world)",
    )

    ## Test with random set that it produces a valid query in bigquery
    struct_tuple2 = structify(data=rand_lat_lons, aliases=aliases)
    query_str = f"""SELECT {",".join(aliases)} FROM UNNEST([{struct_tuple2}])"""
    is_valid, error_msg = is_valid_query(query_str)
    assert is_valid, error_msg
