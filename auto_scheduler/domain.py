from dataclasses import dataclass

from satnogs_predict import ObservationWindow, Satellite as PredictSatellite, TimeRange


@dataclass(frozen=True, slots=True)
class TransmitterInfo:
    norad_cat_id: int
    uuid: str
    success_rate: float
    good_count: int
    data_count: int
    mode: str


@dataclass(slots=True)
class PredictedPass:
    window: ObservationWindow
    satellite: PredictSatellite
    transmitter: TransmitterInfo
    priority: float = 0.0


@dataclass(frozen=True, slots=True)
class ScheduledObservation:
    time_range: TimeRange
    transmitter_uuid: str
    norad_cat_id: int | None
