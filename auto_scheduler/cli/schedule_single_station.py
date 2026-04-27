#!/usr/bin/env python3

# pylint: disable=consider-using-f-string

from __future__ import division

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

from tqdm import tqdm

from auto_scheduler import __version__ as auto_scheduler_version
from auto_scheduler import settings
from auto_scheduler.cache import CacheManager
from auto_scheduler.io import read_priorities_transmitters
from auto_scheduler.pass_predictor import create_observer, find_constrained_passes
from auto_scheduler.satnogs_client import (
    APIRequestError,
    check_station_availability,
    get_groundstation_info,
    get_scheduled_passes_from_network,
    schedule_observations_batch,
)
from auto_scheduler.schedulers import ordered_scheduler, report_efficiency
from auto_scheduler.utils import (
    SatelliteConstraints,
    get_priority_passes,
    print_scheduledpass_summary,
    satellites_by_norad_from_transmitters,
    search_transmitters,
    print_using_tqdm,
)

_LOG_LEVEL_STRINGS = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]


def _log_level_string_to_int(log_level_string):
    if log_level_string not in _LOG_LEVEL_STRINGS:
        message = "invalid choice: {0} (choose from {1})".format(
            log_level_string, _LOG_LEVEL_STRINGS
        )
        raise argparse.ArgumentTypeError(message)

    log_level_int = getattr(logging, log_level_string, logging.INFO)
    # check the logging log_level_choices have not changed from our expected values
    assert isinstance(log_level_int, int)

    return log_level_int


def main():  # noqa: C901
    # pylint: disable=too-many-branches,too-many-statements,too-many-locals

    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Automatically schedule observations on a SatNOGS station."
    )
    parser.add_argument("-s", "--station", help="Ground station ID", type=int)
    parser.add_argument(
        "-t",
        "--starttime",
        help="Start time (YYYY-MM-DDTHH:MM:SS) [default: now + 10 minutes]",
        default=(datetime.now(timezone.utc) + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S"),
    )
    parser.add_argument(
        "-d",
        "--duration",
        help="Duration to schedule [hours; default: 1.0]",
        type=float,
        default=1.0,
    )
    parser.add_argument(
        "-o",
        "--max-observation-duration",
        help="Max time for a single observation [minutes; default: 30]",
        type=float,
        default=30.0,
    )
    parser.add_argument(
        "-m",
        "--min-culmination",
        help="Minimum culmination elevation [degrees; "
        + "ground station default, minimum: 0, maximum: 90]",
        type=float,
        default=None,
    )
    parser.add_argument(
        "-r",
        "--min-riseset",
        help="Minimum rise/set elevation [degrees; "
        + "ground station default, minimum: 0, maximum: 90]",
        type=float,
        default=None,
    )
    parser.add_argument(
        "-z",
        "--horizon",
        help="Force rise/set elevation to 0 degrees (overrided -r).",
        action="store_true",
    )
    parser.add_argument(
        "-b",
        "--start-azimuth",
        help="Start of the azimuth window to observe within. Window goes from start"
        "to stop azimuth in a clockwise direction. [degrees; default: 0, "
        "maximum: 360]",
        type=float,
        default=0.0,
    )
    parser.add_argument(
        "-e",
        "--stop-azimuth",
        help="End of the azimuth window to observe within. Window goes from start "
        "to stop azimuth in a clockwise direction. [degrees; default: 360, "
        "maximum: 360]",
        type=float,
        default=360.0,
    )
    parser.add_argument(
        "-i",
        "--pointing",
        help="Constrain passes to antenna beam radius "
        "(half beamwidth) and pointing direction. "
        "Examples: antenna pointing straight up, 30 degree radius: '-i 30', "
        "pointing south at horizon: '-i 30 180', "
        "pointing west and 45 degrees up: '-i 30 270 45'. "
        "[degrees; default: None]",
        nargs="*",
        type=float,
    )
    parser.add_argument(
        "-f",
        "--only-priority",
        help="Schedule only priority satellites (from -P file)",
        dest="only_priority",
        action="store_false",
    )
    parser.set_defaults(only_priority=True)
    parser.add_argument(
        "-w",
        "--wait",
        help="Wait time between consecutive observations (for setup and slewing)"
        + " [seconds; default: 0, maximum: 3600]",
        type=int,
        default=0,
    )
    parser.add_argument(
        "-n", "--dryrun", help="Dry run (do not schedule passes)", action="store_true"
    )
    parser.add_argument(
        "-P",
        "--priorities",
        metavar="PRIORITIES_FILE",
        help="File with transmitter priorities. Should have "
        + "columns of the form |NORAD priority UUID| like |43017 0.9"
        + " KgazZMKEa74VnquqXLwAvD|. Priority is fractional, one transmitter "
        + "per line, 1.0 gets maximum priority.",
        default=None,
    )
    parser.add_argument(
        "-M",
        "--min-priority",
        help="Minimum priority. Only schedule passes with a priority higher"
        + "than this limit [default: 0.0, maximum: 1.0]",
        type=float,
        default=0.0,
    )
    parser.add_argument(
        "-T",
        "--allow-testing",
        help="Allow scheduling on stations which are in testing mode [default: False]",
        action="store_true",
    )
    parser.set_defaults(allow_testing=False)
    parser.add_argument(
        "--flush-cache",
        help="Clean the cache and download current transmitters, satellites and TLE.",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-l",
        "--log-level",
        default="INFO",
        dest="log_level",
        type=_log_level_string_to_int,
        nargs="?",
        help="Set the logging output level. {0}".format(_LOG_LEVEL_STRINGS),
    )
    parser.add_argument(
        "--version",
        action="version",
        version="satnogs-auto-scheduler {}".format(auto_scheduler_version),
    )
    args = parser.parse_args()

    # Check arguments
    if args.station is None:
        parser.print_help()
        sys.exit()

    # Setting logging level
    numeric_level = args.log_level
    if not isinstance(numeric_level, int):
        raise ValueError("Invalid log level")
    logging.basicConfig(level=numeric_level, format="%(message)s")

    settings.validate_config()

    # Settings
    ground_station_id = args.station

    if args.duration > 0.0:
        length_hours = args.duration
    else:
        length_hours = 1.0

    if args.wait <= 0:
        wait_time_seconds = 0
    elif args.wait <= 3600:
        wait_time_seconds = args.wait
    else:
        wait_time_seconds = 3600

    if args.min_priority < 0.0:
        min_priority = 0.0
    elif args.min_priority > 1.0:
        min_priority = 1.0
    else:
        min_priority = args.min_priority

    # Set time range
    tnow = datetime.strptime(args.starttime, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    tmin = tnow
    tmax = tnow + timedelta(hours=length_hours)

    # Get ground station information
    try:
        ground_station = get_groundstation_info(ground_station_id)
    except APIRequestError:
        sys.exit(1)

    if not args.dryrun and not check_station_availability(ground_station, args.allow_testing):
        sys.exit(1)

    # Set minimum rise/set elevation
    args_min_rise_set = args.min_riseset if not args.horizon else 0.0

    if args_min_rise_set is not None and not ground_station["horizon_hard_limit"]:
        min_riseset = args_min_rise_set
    else:
        min_riseset = max(ground_station["min_horizon"], args_min_rise_set or 0.0)

    min_riseset = min(90.0, max(min_riseset, 0.0))

    # Set minimum culmination elevation
    if args.min_culmination is not None and not ground_station["min_culmination_hard_limit"]:
        min_culmination = args.min_culmination
    else:
        min_culmination = max(ground_station["min_culmination"], args.min_culmination or 0.0)

    min_culmination = min(90.0, max(min_culmination, 0.0))

    # Set start azimuth viewing window
    if args.start_azimuth < 0.0:
        logging.warning("Azimuth window not in range [0, 360] degrees. Setting to 0 degrees.")
        start_azimuth = 0.0
    elif args.start_azimuth > 360.0:
        logging.warning("Azimuth window not in range [0, 360] degrees. Setting to 360 degrees.")
        start_azimuth = 360.0
    else:
        start_azimuth = args.start_azimuth

    # Set stop azimuth viewing window
    if args.stop_azimuth < 0.0:
        logging.warning("Azimuth window not in the range [0, 360] degrees. Setting to 0 degrees.")
        stop_azimuth = 0.0
    elif args.stop_azimuth > 360.0:
        logging.warning("Azimuth window not in the range [0, 360] degrees. Setting to 360 degrees.")
        stop_azimuth = 360.0
    else:
        stop_azimuth = args.stop_azimuth

    # Set antenna pointing and max angular separation
    max_separation, pointing_az, pointing_el = None, 0.0, 90.0
    if args.pointing:
        if len(args.pointing) >= 1:  # antenna pointing straight up
            max_separation = args.pointing[0]
        if len(args.pointing) == 2:  # antenna pointing along horizon
            pointing_az = args.pointing[1]
            pointing_el = 0.0
        elif len(args.pointing) >= 3:  # antenna pointing az/el
            pointing_az = args.pointing[1]
            pointing_el = args.pointing[2]
        if len(args.pointing) > 3:
            logging.warning("Extra args in --pointing, ignored.")
        if pointing_az < 0.0:
            logging.warning(
                "Azimuth angle not in the range [0, 360] degrees. Setting to 0 degrees."
            )
            pointing_az = 0.0
        elif pointing_az > 360.0:
            logging.warning(
                "Azimuth angle not in the range [0, 360] degrees. Setting to 360 degrees."
            )
            pointing_az = 360.0
        if pointing_el < 0.0:
            logging.warning(
                "Elevation angle not in the range [0, 90] degrees. Setting to 0 degrees."
            )
            pointing_el = 0.0
        elif pointing_el > 90.0:
            logging.warning(
                "Elevation angle not in the range [0, 90] degrees. Setting to 90 degrees."
            )
            pointing_el = 90.0
    angular_separation = max_separation, pointing_az, pointing_el

    max_pass_duration = args.max_observation_duration
    priorities_filename = args.priorities
    only_priority = args.only_priority
    dryrun = args.dryrun
    flush_cache = args.flush_cache

    satellite_constraints: SatelliteConstraints = {
        "skip_frequency_violators": True,
    }

    schedule_single_station(
        ground_station_id,
        wait_time_seconds,
        min_priority,
        tmax,
        tmin,
        ground_station,
        min_culmination,
        min_riseset,
        start_azimuth,
        stop_azimuth,
        max_pass_duration,
        priorities_filename,
        only_priority,
        dryrun,
        angular_separation,
        flush_cache,
        satellite_constraints,
    )


def compare_satellite_lists(satellites_old, satellites_new):
    """
    Check two lists of satellites for equality and provide adequate error output if they
    do not match.
    """
    mismatch_found = False

    if not len(satellites_old) == len(satellites_new):
        print(
            "ERROR: Old and new search method for transmitters yield different number of results"
            f" ({len(satellites_old)} vs {len(satellites_new)})!"
        )
        sys.exit(1)

    for satellite_old, satellite_new in zip(satellites_old, satellites_new):
        if not satellite_old == satellite_new:
            mismatch_found = True
            print(satellite_old)
            print(satellite_new)
            break

    if mismatch_found:
        print("ERROR: Mismatch between new and old transmitter search methods found!")
        sys.exit(1)


def schedule_single_station(
    ground_station_id,
    wait_time_seconds,
    min_priority,
    tmax,
    tmin,
    ground_station,
    min_culmination,
    min_riseset,
    start_azimuth,
    stop_azimuth,
    max_pass_duration,
    priorities_filename,
    only_priority,
    dryrun,
    angular_separation,
    flush_cache,
    satellite_constraints: SatelliteConstraints,
):
    """
    Args:
        satellite_constraints: Constraints that each satellite must fulfill
    """
    # pylint: disable=too-many-arguments,too-many-locals

    # Create or update the transmitter & TLE cache
    cache = CacheManager(
        ground_station_id, ground_station["antenna"], settings.CACHE_DIR, settings.CACHE_AGE
    )
    if flush_cache:
        cache.flush_cache()
    cache.update()
    cache.update_transmitters()

    # Extract interesting transmitters and their corresponding satellites
    transmitters = search_transmitters(
        cache.transmitters_receivable,
        cache.transmitters_stats,
        cache.satellites_by_norad_id,
        satellite_constraints,
    )
    satellites_by_norad = satellites_by_norad_from_transmitters(transmitters, cache.tles_all)

    # Find passes
    constraints = {
        "time": (tmin, tmax),
        "pass_duration": (settings.MIN_PASS_DURATION, max_pass_duration),
        "azimuth": (start_azimuth, stop_azimuth),
        "min_culmination": min_culmination,
        "angular_separation": angular_separation,
    }
    try:
        logging.info("Download list of scheduled passes from SatNOGS Network...")
        scheduled_observations = get_scheduled_passes_from_network(ground_station_id, tmin, tmax)
    except APIRequestError:
        logging.error("Download from SatNOGS Network failed.")
        sys.exit(1)

    logging.info(
        f"Found {len(scheduled_observations)} scheduled passes "
        f"between {tmin} and {tmax} on ground station {ground_station_id}."
    )

    occupied_ranges = [
        scheduled_observation.time_range for scheduled_observation in scheduled_observations
    ]

    logging.info(
        f"Search passes for {len(transmitters)} transmitters across "
        f"{len(satellites_by_norad)} satellites:"
    )

    # Set observer
    observer = create_observer(
        ground_station["lat"],
        ground_station["lng"],
        ground_station["altitude"],
        min_riseset=min_riseset,
    )
    passes = []
    for transmitter in tqdm(transmitters, disable=None):
        satellite = satellites_by_norad.get(transmitter.norad_cat_id)
        if satellite is None:
            logging.warning(
                "No TLE found for transmitter %s on NORAD %s, skipping.",
                transmitter.uuid,
                transmitter.norad_cat_id,
            )
            continue
        with print_using_tqdm():
            passes.extend(
                find_constrained_passes(
                    satellite,
                    transmitter,
                    observer,
                    constraints,
                    scheduled_intervals=occupied_ranges,
                )
            )

    priorities, favorite_transmitters = read_priorities_transmitters(priorities_filename)

    # Get passes of priority objects
    prioritypasses, normalpasses = get_priority_passes(
        passes, priorities, favorite_transmitters, only_priority, min_priority
    )

    # Priority scheduler
    prioritypasses = sorted(prioritypasses, key=lambda predicted_pass: -predicted_pass.priority)
    selected_prioritypasses = ordered_scheduler(prioritypasses, occupied_ranges, wait_time_seconds)

    # Normal scheduler
    normalpasses = sorted(normalpasses, key=lambda predicted_pass: -predicted_pass.priority)
    selected_normalpasses = ordered_scheduler(normalpasses, occupied_ranges, wait_time_seconds)
    selected_passes = selected_prioritypasses + selected_normalpasses

    # Report scheduling efficiency
    report_efficiency(selected_passes, passes)

    print_scheduledpass_summary(
        scheduled_observations,
        selected_passes,
        ground_station_id,
        cache.satellites_by_norad_id,
        printer=logging.info,
    )

    # Login and schedule passes
    passes_schedule = sorted(
        selected_passes,
        key=lambda predicted_pass: predicted_pass.window.start_sample.instant.to_datetime(),
    )
    if (not dryrun) and passes_schedule:
        logging.info("Scheduling all unscheduled passes listed above.")
        observations = list(
            {
                "ground_station_id": ground_station_id,
                "transmitter_uuid": predicted_pass.transmitter.uuid,
                "start": predicted_pass.window.start_sample.instant.to_datetime(),
                "end": predicted_pass.window.end_sample.instant.to_datetime(),
            }
            for predicted_pass in passes_schedule
        )
        schedule_observations_batch(observations)

    logging.info("Done.")
