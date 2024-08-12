import pytest

from auto_scheduler.satnogs_client import (
    get_active_transmitter_info,
    get_groundstation_info,
    get_satellite_info,
    get_tles,
    get_transmitter_stats,
)


def test_get_groundstation_info():
    """
    Test the get_groundstation_info method.

    Check that station information is returned for the requested station.

    Requires SatNOGS Network to be online.
    """
    ground_station_id = 2
    ground_station = get_groundstation_info(ground_station_id)

    assert isinstance(ground_station, dict)
    assert "id" in ground_station
    assert ground_station["id"] == ground_station_id


def test_get_satellite_info():
    """
    Unit test for get_satellite_info
    """
    satellites_list = get_satellite_info()

    assert isinstance(satellites_list, list)
    assert "norad_cat_id" in satellites_list[0]


def test_get_active_transmitter_info():
    fmin, fmax = 430_000_000, 470_000_000
    transmitters = get_active_transmitter_info(fmin, fmax)
    assert isinstance(transmitters, list)
    assert isinstance(transmitters[0], dict)
    assert "mode" in transmitters[0]
    assert "norad_cat_id" in transmitters[0]
    assert "uuid" in transmitters[0]


def test_get_tles():
    """
    Unit test for get_tles
    """
    tles = get_tles()
    assert isinstance(tles, list)


@pytest.mark.skip(reason="slow, approx. 4min; requires pagination through >50 pages")
def test_get_transmitter_stats():
    """
    Unit test for get_transmitter_stats
    """
    transmitters = get_transmitter_stats()
    assert isinstance(transmitters, list)
