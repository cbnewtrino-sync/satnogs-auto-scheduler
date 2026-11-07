import json
import tempfile

import pytest

from auto_scheduler.cache import CacheManager
from auto_scheduler.utils import search_satellites, search_transmitters


def key2int(dict_object):
    """
    Convert all keys to integer
    """
    return {int(key): value for key, value in dict_object.items()}


def test_search_satellites():
    """
    Unit test for search_satellites using data for a typical UHF station.
    """
    # Load input data
    with open("./tests/fixtures/transmitters_receivable.json") as fp_transmitters2:
        transmitters_receivable = json.load(fp_transmitters2)

    with open("./tests/fixtures/transmitters_stats.json") as fp_transmitters_stats:
        transmitters_stats = json.load(fp_transmitters_stats)

    with open("./tests/fixtures/tles.json") as fp_tles:
        tles_all = json.load(fp_tles)

    with open("./tests/fixtures/satellites.json") as fp_satellites:
        satellites_by_norad_id_str = json.load(fp_satellites)
    satellites_by_norad_id = key2int(satellites_by_norad_id_str)

    # Load output data
    with open("./tests/fixtures/search_satellites_output.json") as fp_output:
        norad_cat_ids_fixture = set(json.load(fp_output))

    satellites = search_satellites(
        transmitters_receivable,
        transmitters_stats,
        tles_all,
        satellites_by_norad_id,
    )
    norad_cat_ids = set(int(sat.identifier) for sat in satellites)

    assert norad_cat_ids == norad_cat_ids_fixture


@pytest.mark.skip(reason="takes approx. 4 minutes due to the transmitter statistics download")
def test_search_satellites_online():
    """
    Check that search_satellites does not return satellites with temporary norad id (>90000):
    """
    ground_station_id = 1888
    ground_station_antenna = [
        {
            "antenna_type": "yagi",
            "antenna_type_name": "Yagi",
            "band": "UHF",
            "frequency": 430000000,
            "frequency_max": 446000000,
        }
    ]
    cache_age = 24  # hours

    with tempfile.TemporaryDirectory() as cache_dir:
        cache = CacheManager(ground_station_id, ground_station_antenna, cache_dir, cache_age)
        cache.update()

    satellites = search_satellites(
        cache.transmitters_receivable,
        cache.transmitters_stats,
        cache.tles_all,
        cache.satellites_by_norad_id,
    )

    for satellite in satellites:
        assert int(satellite.identifier) < 90000


def _load_search_inputs():
    with open("./tests/fixtures/transmitters_receivable.json") as fp:
        transmitters_receivable = json.load(fp)
    with open("./tests/fixtures/transmitters_stats.json") as fp:
        transmitters_stats = json.load(fp)
    with open("./tests/fixtures/satellites.json") as fp:
        satellites_by_norad_id = key2int(json.load(fp))
    return transmitters_receivable, transmitters_stats, satellites_by_norad_id


def test_search_transmitters_min_success_rate():
    receivable, stats, satellites = _load_search_inputs()

    unfiltered = search_transmitters(receivable, stats, satellites)
    default = search_transmitters(receivable, stats, satellites, min_success_rate=0.0)
    assert [t.uuid for t in default] == [t.uuid for t in unfiltered]

    filtered = search_transmitters(receivable, stats, satellites, min_success_rate=50.0)
    expected = [t.uuid for t in unfiltered if stats[t.uuid]["success_rate"] >= 50]
    assert [t.uuid for t in filtered] == expected
    assert 0 < len(filtered) < len(unfiltered)
    assert all(t.success_rate >= 0.5 for t in filtered)


def test_search_transmitters_min_success_rate_exempt():
    receivable, stats, satellites = _load_search_inputs()

    unfiltered = search_transmitters(receivable, stats, satellites)
    low = next(t for t in unfiltered if stats[t.uuid]["success_rate"] < 50)

    filtered = search_transmitters(
        receivable, stats, satellites, min_success_rate=50.0, exempt_uuids={low.uuid}
    )
    assert low.uuid in [t.uuid for t in filtered]


def test_search_transmitters_success_min_count():
    receivable, stats, satellites = _load_search_inputs()

    unfiltered = search_transmitters(receivable, stats, satellites)
    filtered = search_transmitters(
        receivable, stats, satellites, min_success_rate=50.0, success_min_count=20
    )
    expected = [
        t.uuid
        for t in unfiltered
        if stats[t.uuid]["success_rate"] >= 50 or stats[t.uuid]["total_count"] < 20
    ]
    assert [t.uuid for t in filtered] == expected
