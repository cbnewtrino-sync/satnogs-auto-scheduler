import contextlib
import inspect
import logging
from datetime import timezone
from typing import Any, TypedDict

from satnogs_predict import Satellite as PredictSatellite
from tqdm import tqdm

from auto_scheduler.domain import PredictedPass, ScheduledObservation, TransmitterInfo
from auto_scheduler.tle import parse_tle0


class SatelliteConstraints(TypedDict):
    skip_frequency_violators: bool


def get_priority_passes(
    passes: list[PredictedPass],
    priorities,
    favorite_transmitters,
    only_priority,
    min_priority,
):
    priority = []
    normal = []
    for predicted_pass in passes:
        satellite_id = predicted_pass.satellite.identifier
        # Is this satellite a priority satellite?
        # Is this transmitter a favorite transmitter?
        # Is the priority high enough?
        if (
            satellite_id in priorities
            and predicted_pass.transmitter.uuid == favorite_transmitters[satellite_id]
            and priorities[satellite_id] >= min_priority
        ):
            predicted_pass.priority = priorities[satellite_id]
            priority.append(predicted_pass)
        elif only_priority:
            # Find satellite transmitter with highest number of good observations
            max_good_count = max(
                candidate.transmitter.good_count
                for candidate in passes
                if candidate.satellite.identifier == satellite_id
            )
            max_altitude_deg = predicted_pass.window.max_altitude_sample.altitude_deg
            if max_good_count > 0:
                predicted_pass.priority = (
                    (max_altitude_deg / 90.0)
                    * predicted_pass.transmitter.success_rate
                    * float(predicted_pass.transmitter.good_count)
                    / max_good_count
                )
            else:
                predicted_pass.priority = (
                    max_altitude_deg / 90.0
                ) * predicted_pass.transmitter.success_rate

            # Add if priority is high enough
            if predicted_pass.priority >= min_priority:
                normal.append(predicted_pass)
    return (priority, normal)


def satellite_from_tle(tle: dict[str, Any]) -> PredictSatellite:
    return PredictSatellite.from_tle(
        line0=tle["tle0"],
        line1=tle["tle1"],
        line2=tle["tle2"],
        identifier=str(tle["norad_cat_id"]),
    )


def satellites_by_norad_from_transmitters(
    transmitters: list[TransmitterInfo], tles: list[dict[str, Any]]
) -> dict[int, PredictSatellite]:
    satellites_by_norad: dict[int, PredictSatellite] = {}
    norad_ids = {transmitter.norad_cat_id for transmitter in transmitters}

    for tle in tles:
        norad_cat_id = tle["norad_cat_id"]
        if norad_cat_id in norad_ids and norad_cat_id not in satellites_by_norad:
            satellites_by_norad[norad_cat_id] = satellite_from_tle(tle)

    return satellites_by_norad


# def satellites_from_transmitters(
#     transmitters: list[TransmitterInfo], tles: list[dict[str, Any]]
# ) -> list[PredictSatellite]:
#     """
#     Extract satellites of interest based on the list of transmitters of interest

#     # Arguments
#     transmitters (list): List of transmitters of interest
#     tles (list): List of TLEs for all satellites

#     # Returns
#     List of satellites

#     # Return type
#     list(satnogs_predict.Satellite)
#     """
#     satellites: list[PredictSatellite] = []
#     for transmitter in transmitters:
#         for tle in tles:
#             if tle["norad_cat_id"] == transmitter.norad_cat_id:
#                 satellites.append(satellite_from_tle(tle))
#     return satellites


def search_transmitters(
    transmitters_receivable,
    transmitters_stats,
    satellites_by_norad_id,
    satellite_constraints: SatelliteConstraints = {
        "skip_frequency_violators": True,
    },
    min_success_rate: float = 0.0,
    success_min_count: int = 0,
    exempt_uuids=frozenset(),
) -> list[TransmitterInfo]:
    """
    Extract satellites of interest based on the list of transmitters of interest

    Transmitters whose SatNOGS Network success rate is below min_success_rate (percent,
    0-100, the number shown on the network website) are skipped, unless their uuid is in
    exempt_uuids (e.g. favourite transmitters from the priorities file) or they have fewer
    than success_min_count observations in total (too little history to judge).

    NOTE:
    The transmitter mode is truncated. This was done in previous versions of the auto-scheduler
    probably by accident (un-escaped whitespace in a whitespace-seperated text file), for
    backward compatibility now. Can be removed if all code using this object is validated against
    using the full 'mode' text string.

    # Arguments
    transmitters_receivable (dict): Receivable transmitters keyed by UUID
    transmitters_stats (dict): Transmitter statistics keyed by UUID
    satellite_constraints: Constraints that each transmitter's satellite must fulfill

    # Returns
    List of transmitters of interest
    """
    norad_cat_ids_alive = satellites_by_norad_id.keys()

    # Filter transmitters based on ground station capability
    transmitters_of_interest: list[TransmitterInfo] = []
    n_low_success = 0

    for uuid, stats in transmitters_stats.items():
        # Skip transmitters which do not have statistics in SatNOGS Network (yet)

        if uuid not in transmitters_receivable:
            continue

        # Skip dead satellites
        if transmitters_receivable[uuid]["norad_cat_id"] not in norad_cat_ids_alive:
            continue

        # Skip satellites with frequency misuse (avoids scheduling permission errors)
        if satellite_constraints["skip_frequency_violators"]:
            norad = transmitters_receivable[uuid]["norad_cat_id"]
            if satellites_by_norad_id[norad]["is_frequency_violator"]:
                continue

        # Skip historically unproductive transmitters
        if (
            min_success_rate > 0.0
            and stats["success_rate"] < min_success_rate
            and uuid not in exempt_uuids
            and stats["total_count"] >= success_min_count
        ):
            n_low_success += 1
            continue

        transmitters_of_interest.append(
            TransmitterInfo(
                norad_cat_id=transmitters_receivable[uuid]["norad_cat_id"],
                uuid=uuid,
                success_rate=stats["success_rate"] / 100.0,
                good_count=stats["good_count"],
                data_count=stats["total_count"],
                mode=str(transmitters_receivable[uuid]["mode"]).split()[0],
            )
        )
    if n_low_success:
        logging.info(
            f"Skipped {n_low_success} transmitters with success rate below "
            f"{min_success_rate:g}%."
        )
    return transmitters_of_interest


def search_satellites(
    transmitters_receivable,
    transmitters_stats,
    tles_all,
    satellites_by_norad_id,
    satellite_constraints: SatelliteConstraints = {
        "skip_frequency_violators": True,
    },
) -> list[PredictSatellite]:
    """
    Compatibility helper that returns unique satellites for the selected transmitters.
    """
    transmitters = search_transmitters(
        transmitters_receivable,
        transmitters_stats,
        satellites_by_norad_id,
        satellite_constraints,
    )
    return list(satellites_by_norad_from_transmitters(transmitters, tles_all).values())


def _format_utc_datetime(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def print_scheduledpass_summary(
    scheduled_observations: list[ScheduledObservation],
    selected_passes: list[PredictedPass],
    ground_station_id,
    satellites_catalog,
    printer=print,
):
    printer(
        "  GS | Sch | NORAD | Start time          | End time            | Duration | AzR El AzS | "
        + "Priority | Transmitter UUID       | Mode        | Freq   | Satellite name"
    )
    printer(f"{' ' * 136} | misuse | ")

    rows = [
        (scheduled_observation.time_range.start.to_datetime(), scheduled_observation)
        for scheduled_observation in scheduled_observations
    ] + [
        (predicted_pass.window.start_sample.instant.to_datetime(), predicted_pass)
        for predicted_pass in selected_passes
    ]

    for _, entry in sorted(rows, key=lambda row: row[0]):
        if isinstance(entry, ScheduledObservation):
            start = entry.time_range.start.to_datetime()
            end = entry.time_range.end.to_datetime()
            sat_entry = satellites_catalog.get(entry.norad_cat_id, {})
            printer(
                f"{ground_station_id:4d} | "
                f"{'Y':3s} | "
                f"{int(entry.norad_cat_id or 0):05d} | "
                f"{_format_utc_datetime(start):s} | "
                f"{_format_utc_datetime(end):s} | "
                f"{str(end - start).split('.', maxsplit=1)[0]:>8} | "
                f"{0.0:3.0f} {0.0:2.0f} {0.0:3.0f} | "
                f"{1.0:4.6f} | "
                f"{entry.transmitter_uuid:s} | "
                f"{'':<11s} | "
                f"{'Y' if sat_entry.get('is_frequency_violator') else 'N':6s} | "
                f"{sat_entry.get('name', ''):s}"
            )
            continue

        start = entry.window.start_sample.instant.to_datetime()
        end = entry.window.end_sample.instant.to_datetime()
        norad_cat_id = int(entry.satellite.identifier)
        sat_entry = satellites_catalog[norad_cat_id]
        printer(
            f"{ground_station_id:4d} | "
            f"{'N':3s} | "
            f"{norad_cat_id:05d} | "
            f"{_format_utc_datetime(start):s} | "
            f"{_format_utc_datetime(end):s} | "
            f"{str(end - start).split('.', maxsplit=1)[0]:>8} | "
            f"{entry.window.start_sample.azimuth_deg:3.0f} "
            f"{entry.window.max_altitude_sample.altitude_deg:2.0f} "
            f"{entry.window.end_sample.azimuth_deg:3.0f} | "
            f"{entry.priority:4.6f} | "
            f"{entry.transmitter.uuid:s} | "
            f"{entry.transmitter.mode:<11s} | "
            f"{'Y' if sat_entry['is_frequency_violator'] else 'N':6s} | "
            f"{parse_tle0(entry.satellite.orbit.data.line0):s}"
        )


@contextlib.contextmanager
def print_using_tqdm():
    _print = print

    def print2(obj, *, end="\n", file=None):
        """
        original signature:
            print(*objects, *, sep=' ', end='\n', file=None, flush=False)
        """
        try:
            tqdm.write(obj, end=end, file=file)
        except OSError:
            # Try to use original print instead
            _print(obj, end=end, file=file)

    try:
        inspect.builtins.print = print2
        yield
    finally:
        inspect.builtins.print = _print
