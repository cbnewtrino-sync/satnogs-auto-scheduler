import logging
from datetime import timedelta

from satnogs_predict import (
    AngularSeparationConstraint,
    AzimuthWindowConstraint,
    Duration,
    MaxDurationConstraint,
    MinCulminationConstraint,
    MinDurationConstraint,
    Observer,
    OverlapHandling,
    PlanningConfig,
    Satellite as PredictSatellite,
    TimeRange,
    find_observation_windows,
)

from auto_scheduler.domain import PredictedPass, TransmitterInfo

logger = logging.getLogger(__name__)


def _satellite_norad_id(satellite: PredictSatellite) -> int:
    return int(satellite.identifier)


def create_observer(lat, lon, alt, min_riseset=0.0):
    """Create a satnogs_predict observer instance."""
    return Observer(
        lat_deg=float(lat),
        lon_deg=float(lon),
        elevation_meters=int(alt),
        horizon_deg=float(min_riseset),
        identifier=f"{lat}:{lon}:{alt}:{min_riseset}",
    )


def find_constrained_passes(
    satellite: PredictSatellite,
    transmitter: TransmitterInfo,
    observer: Observer,
    constraints,
    scheduled_intervals=None,
):
    """
    Find passes of one satellite over a specified ground station while
    taking multiple constraints into account.
    """
    tmin, tmax = constraints["time"]
    min_pass_duration, max_pass_duration = constraints["pass_duration"]
    start_azimuth, stop_azimuth = constraints["azimuth"]
    min_culmination = constraints["min_culmination"]
    angular_separation = constraints["angular_separation"]

    if scheduled_intervals is None:
        scheduled_intervals = []

    time_range = TimeRange.from_datetimes(tmin, tmax)
    planning_config = PlanningConfig(
        overlap_handling=OverlapHandling.DROP,
        split_long_windows=False,
    )

    min_duration_constraint = MinDurationConstraint(
        Duration.from_timedelta(timedelta(minutes=min_pass_duration))
    )
    min_culmination_constraint = MinCulminationConstraint(min_culmination)
    max_duration_constraint = MaxDurationConstraint(
        Duration.from_timedelta(timedelta(minutes=max_pass_duration)),
        trim=True,
    )

    pre_plan_constraints = [
        min_duration_constraint,
        min_culmination_constraint,
    ]
    post_plan_constraints = [
        max_duration_constraint,
        min_duration_constraint,
        min_culmination_constraint,
    ]

    if not (start_azimuth == 0.0 and stop_azimuth == 360.0):
        azimuth_constraint = AzimuthWindowConstraint(start_azimuth, stop_azimuth)
        pre_plan_constraints.append(azimuth_constraint)

    max_separation, pointing_az, pointing_el = angular_separation
    if max_separation:
        angular_constraint = AngularSeparationConstraint(
            max_separation_deg=max_separation,
            pointing_az_deg=pointing_az,
            pointing_el_deg=pointing_el,
            min_duration=Duration.from_timedelta(timedelta(minutes=min_pass_duration)),
        )
        pre_plan_constraints.append(angular_constraint)

    valid_windows, rejected_windows = find_observation_windows(
        satellite=satellite,
        observer=observer,
        time_range=time_range,
        planning_config=planning_config,
        pre_plan_constraints=pre_plan_constraints,
        post_plan_constraints=post_plan_constraints,
        scheduled_intervals=scheduled_intervals,
    )

    for rejected in rejected_windows:
        logger.debug(
            "Rejected pass for %s: %s",
            _satellite_norad_id(satellite),
            rejected.rejection_reason,
        )

    return [
        PredictedPass(
            window=window,
            satellite=satellite,
            transmitter=transmitter,
        )
        for window in valid_windows
    ]
