"""
Unit tests for the pass predictor
"""

import datetime

import tomllib

from auto_scheduler.io import read_tles, read_transmitters_of_interest
from auto_scheduler.pass_predictor import create_observer, find_constrained_passes
from auto_scheduler.utils import satellites_by_norad_from_transmitters

TIMEDELTA_RESOLUTION = 1  # seconds
ANGLE_RESOLUTION = 1  # degrees
MAX_PASS_DURATION = 1000  # minutes


def as_utc(dt):
    return dt.replace(tzinfo=datetime.timezone.utc) if dt.tzinfo is None else dt


def assert_pass(predicted_pass, expected_pass):
    """
    Check that both provided passes are equal in rise & set times and locations.
    """
    window = predicted_pass.window
    actual_times = {
        "start": window.start_sample.instant.to_datetime(),
        "culmination": window.max_altitude_sample.instant.to_datetime(),
        "end": window.end_sample.instant.to_datetime(),
    }
    actual_angles = {
        "start_azimuth": window.start_sample.azimuth_deg,
        "culmination_altitude": window.max_altitude_sample.altitude_deg,
        "end_azimuth": window.end_sample.azimuth_deg,
    }

    for key, actual in actual_times.items():
        expected = as_utc(expected_pass[key])
        assert abs((actual - expected).total_seconds()) < TIMEDELTA_RESOLUTION

    for key, actual in actual_angles.items():
        assert abs(actual - expected_pass[key]) < ANGLE_RESOLUTION


def test_find_passes():
    """
    Test the find_passes method with a number of satellites
    """

    with open("tests/fixtures/pass_prediction1.toml", "rb") as test_case_file:
        test_case = tomllib.load(test_case_file)

    tles = list(read_tles(test_case["files"]["tles_filename"]))
    transmitters = list(read_transmitters_of_interest(test_case["files"]["transmitters_filename"]))

    # Extract interesting satellites from receivable transmitters
    satellites_by_norad = satellites_by_norad_from_transmitters(transmitters, tles)

    # Find all passes for station 2, given the transmitters and tles
    observer = create_observer(
        test_case["ground_station"]["lat"],
        test_case["ground_station"]["lng"],
        test_case["ground_station"]["altitude"],
        min_riseset=test_case["ground_station"]["min_horizon"],
    )

    constraints = {
        "time": (as_utc(test_case["tmin"]), as_utc(test_case["tmax"])),
        "pass_duration": (test_case["min_pass_duration"], MAX_PASS_DURATION),
        "azimuth": (0.0, 360.0),
        "min_culmination": test_case["min_culmination"],
        "angular_separation": (None, 0.0, 0.0),
    }

    # Loop over transmitters
    passes = []
    for transmitter in transmitters:
        satellite = satellites_by_norad.get(transmitter.norad_cat_id)
        if satellite is None:
            continue

        passes.extend(
            find_constrained_passes(
                satellite,
                transmitter,
                observer,
                constraints,
            )
        )

    # Check that the expected number of passes was found
    assert len(passes) == test_case["passes"]["count"]

    # Make sure the start/culmination/end samples match the expected first pass
    assert_pass(passes[0], test_case["passes"]["first_pass"])
