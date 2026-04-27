import logging
import random

from satnogs_predict import Duration, TimeRange, has_range_list_overlap

from auto_scheduler.domain import PredictedPass


def _predicted_pass_to_time_range(predicted_pass: PredictedPass):
    return TimeRange.from_datetimes(
        predicted_pass.window.start_sample.instant.to_datetime(),
        predicted_pass.window.end_sample.instant.to_datetime(),
    )


def _overlaps_existing(predicted_pass, occupied_ranges, wait_time_seconds):
    ordered_ranges = sorted(
        occupied_ranges + [_predicted_pass_to_time_range(predicted_pass)],
        key=lambda time_range: time_range.start,
    )
    return has_range_list_overlap(
        ordered_ranges,
        padding=Duration.from_seconds(wait_time_seconds),
    )


def ordered_scheduler(passes, occupied_ranges, wait_time_seconds):
    """Loop through a list of ordered passes and schedule each next one that fits"""
    selected_passes = []
    # Loop over passes
    for predicted_pass in passes:
        # Schedule if there is no overlap with already scheduled passes
        if not _overlaps_existing(predicted_pass, occupied_ranges, wait_time_seconds):
            occupied_ranges.append(_predicted_pass_to_time_range(predicted_pass))
            selected_passes.append(predicted_pass)

    return selected_passes


def random_scheduler(passes, occupied_ranges, wait_time_seconds):
    """Schedule passes based on random ordering"""
    # Shuffle passes
    random.shuffle(passes)

    return ordered_scheduler(passes, occupied_ranges, wait_time_seconds)


def report_efficiency(selected_passes, passes):
    if selected_passes:
        # Loop over passes
        start = False
        for predicted_pass in selected_passes:
            start_dt = predicted_pass.window.start_sample.instant.to_datetime()
            end_dt = predicted_pass.window.end_sample.instant.to_datetime()
            if not start:
                duration_scheduled = end_dt - start_dt
                tmin = start_dt
                tmax = end_dt
                start = True
            else:
                duration_scheduled += end_dt - start_dt
                if start_dt < tmin:
                    tmin = start_dt
                if end_dt > tmax:
                    tmax = end_dt
        # Total time covered
        duration_total = tmax - tmin

        efficency = 100 * duration_scheduled.total_seconds() / duration_total.total_seconds()
        logging.info(
            f"{len(selected_passes)} passes selected out of {len(passes)}, "
            f"{duration_scheduled.total_seconds():.0f} s out of "
            f"{duration_total.total_seconds():.0f} s "
            f"at {efficency:.3f}% efficiency"
        )

    else:
        logging.info("No appropriate passes found for scheduling.")
