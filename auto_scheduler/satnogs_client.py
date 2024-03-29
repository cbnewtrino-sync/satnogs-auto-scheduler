import logging
import sys
from datetime import datetime

import requests

from auto_scheduler import settings

logger = logging.getLogger(__name__)

TIMEOUT = 30  # seconds


class APIRequestError(IOError):
    """
    There was an error fetching the requested resource, e.g.
    HTTPError, ConnectionError, Timeout
    """


def get_paginated_endpoint(url,
                           max_entries=None,
                           token=None,
                           max_retries=0,
                           filter_output_callback=None,
                           stop_criterion_callback=None):
    # pylint: disable=too-many-arguments
    """
    Fetch data from a SatNOGS Network/DB API endpoint.

    Arguments
    url (str):          The URL of the API endpoint
    max_entries (int):  The maximum number of requested entries. This allows indirect limiting
                        of the number of pages to be fetched.
                        Returned data might have slightly more elements.
                        Default: None - Fetch all available pages
    token (str):        Authorization Token.
                        Default: None - Use no authentication.
    timeout (int):      Requests timeout in Seconds
                        Default: 3 Seconds
    max_retries (int) : The maximum number of retries to attempt per request.
                        This applies only to failed DNS lookups, socket connections and
                        connection timeouts.
                        Default: 0 - No retries.
    """
    try:
        session = requests.Session()
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=max_retries))

        if token:
            headers = {'Authorization': f'Token {token}'}
        else:
            headers = None

        data = []

        response = session.get(url=url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()

        new_data = response.json()

        if len(new_data) == 0:
            return []

        if filter_output_callback:
            data.extend(filter_output_callback(new_data))
        else:
            data.extend(new_data)

        if stop_criterion_callback and stop_criterion_callback(new_data):
            return data

        while 'next' in response.links and (not max_entries or len(data) < max_entries):
            url = response.links['next']['url']

            response = session.get(url=url, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()

            new_data = response.json()
            if filter_output_callback:
                data.extend(filter_output_callback(new_data))
            else:
                data.extend(new_data)

            if stop_criterion_callback and stop_criterion_callback(new_data):
                break
    except requests.HTTPError as exception:
        err = response.json()
        logger.error(f'API Request for {url} failed, error: {err}')
        raise APIRequestError from exception
    except requests.exceptions.ReadTimeout as exception:
        logger.error(f'Timeout after {TIMEOUT} seconds while requesting {url}')
        raise APIRequestError from exception

    return data


def get_satellite_info():
    """
    Fetch all satellites from SatNOGS DB
    """
    return get_paginated_endpoint(f'{settings.DB_BASE_URL}/api/satellites')


def get_active_transmitter_info(fmin, fmax):
    """
    Fetch all transmitters from SatNOGS DB.

    The transmitters are filtered for the following criteria:
    - 'status': active
    - 'dowlink_low' is defined
    - 'downlink_low' within (fmin, fmax] frequency band
    - associated with a satellite, via 'norad_cat_id'
    """
    transmitters = get_paginated_endpoint(f'{settings.DB_BASE_URL}/api/transmitters')

    transmitters_filtered = []
    for entry in transmitters:
        if not entry["downlink_low"]:
            continue
        if not entry["status"] == "active":
            continue
        if not fmin < entry["downlink_low"] <= fmax:
            continue
        if entry["norad_cat_id"] is None:
            continue

        transmitter = {
            "norad_cat_id": entry["norad_cat_id"],
            "uuid": entry["uuid"],
            "mode": entry["mode"]
        }
        transmitters_filtered.append(transmitter)

    return transmitters_filtered


def get_tles():
    """
    Fetch latest TLEs from SatNOGS DB.
    """
    tle_data = get_paginated_endpoint(f'{settings.DB_BASE_URL}/api/tle/',
                                      token=settings.SATNOGS_DB_API_TOKEN)
    return tle_data


def get_transmitter_stats():
    """
    Fetch transmitter statistics from SatNOGS Network.

    # Note
    This operation takes some minutes. It fetches many pages
    (78 pages as of 2023-01, ~4min wall clock time). Cache wisely!
    """
    transmitters = get_paginated_endpoint(f'{settings.NETWORK_BASE_URL}/api/transmitters/')
    return transmitters


def get_scheduled_passes_from_network(ground_station, tmin, tmax):
    """
    Fetch observations for a specific ground station and time range from SatNOGS Network.

    # Note
    This algorithm is based on the order in which the API returns the observations, i.e.
    most recent observations are returned at first! It fetches observations until the end of
    the last fetched observation happens to be before the start time of the selected time range.

    # Arguments
    ground_station (int): Ground Station ID
    tmin (datetime.datetime): Filter start time
    tmax (datetime.datetime): Filter end time
    """

    def filter_callback(data):
        scheduled_passes = []
        for obs in data:
            start = datetime.strptime(obs['start'].replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
            end = datetime.strptime(obs['end'].replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
            satpass = {
                "tr": start,
                "ts": end,
                "td": end - start,
                "scheduled": True,
                "altt": obs['max_altitude'],
                "priority": 1,
                "transmitter": {
                    "uuid": obs['transmitter'],
                    "mode": ''
                },
                "satellite": {
                    "name": '',
                    "id": obs['norad_cat_id']
                }
            }

            if satpass['ts'] > tmin and satpass['tr'] < tmax:
                # Only store observations which are during the ROI for scheduling
                scheduled_passes.append(satpass)
        return scheduled_passes

    def stop_criterion_callback(data):
        # Last fetched observation is older than the ROI for scheduling, end loop.
        end_time = datetime.strptime(data[-1]['end'].replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
        return end_time < tmin

    return get_paginated_endpoint(
        f'{settings.NETWORK_BASE_URL}/api/observations/?ground_station={ground_station}',
        filter_output_callback=filter_callback,
        stop_criterion_callback=stop_criterion_callback)


def get_groundstation_info(ground_station_id):
    """
    Fetch ground station information for the given station from SatNOGS Network.

    Side-effects
    - Logging

    Arguments
    ground_station_id (int): Ground Station ID

    Returns
    (dict): The requested ground station information or None
    """
    stations = get_paginated_endpoint(
        f'{settings.NETWORK_BASE_URL}/api/stations/?id={ground_station_id}')

    selected_stations = list(filter(lambda s: s['id'] == ground_station_id, stations))

    if not selected_stations:
        logger.info('No ground station information found!')
        # Exit if no ground station found
        return None

    return selected_stations[0]


def check_station_availability(station, allow_testing):
    """
    Check if scheduling is possible on the given ground station.

    Side-effects
    - Logging

    Arguments
    station (dict): Ground station information as given by SatNOGS Network
    allow_testing (bool): If true the station is considered available for scheduling
                          also when the station status is testing
    """
    if station['status'] == 'Online' or (station['status'] == 'Testing' and allow_testing):
        return True

    if station['status'] == 'Testing' and not allow_testing:
        logger.info(f"Ground station {station['id']} is in testing mode but auto-scheduling is not "
                    "allowed. Use -T command line argument to enable scheduling.")
    else:
        logger.info(f"Ground station {station['id']} neither in 'online' nor in 'testing' mode, "
                    "can't schedule!")
    return False


def handle_batch_scheduling_error(err):
    """
    Error handling of errors occuring during batch Observation scheduling
    via the SatNOGS Network API.
    """

    logger.error('Failed to batch-schedule observations.')

    if err.get('detail') == 'Invalid token.':
        logger.error('Invalid SATNOGS_API_TOKEN, Please check your configuration; Exiting.')
        sys.exit(1)

    if 'non_field_errors' in err and err['non_field_errors'][
            0][:38] == 'No permission to schedule observations':
        # Typical server response: 'No permission to schedule observations on station: 42'
        logger.error(f'Sever response: {err["non_field_errors"][0]}')
        logger.info("note: This permission error might be specific to only this "
                    "(station, satellite, transmitter) pair.")
    else:
        logger.error(f'Server response: {err}')


def handle_single_scheduling_error(observation, err):
    """
    Error handling of errors occuring during single-observation scheduling
    via the SatNOGS Network API.
    """
    logger.error(f"Failed to schedule pass at {observation['start']:%Y-%m-%dT%H:%M:%S}.")
    if 'non_field_errors' in err:
        logger.error(f"{err['non_field_errors'][0]}.")
        logger.info("note: This error might be specific to only this "
                    "(station, satellite, transmitter) pair.")
    else:
        logger.error(f"{err}.")


def serialize_observation(satpass):
    """
    Convert future observation into the format expected by
    the scheduling endpoint in SatNOGS Network
    """
    return {
        'ground_station': satpass['ground_station_id'],
        'transmitter_uuid': satpass['transmitter_uuid'],
        'start': satpass['start'].strftime("%Y-%m-%d %H:%M:%S"),
        'end': satpass['end'].strftime("%Y-%m-%d %H:%M:%S")
    }


def schedule_observations_batch(observations):
    """
    Schedule observations on satnogs-network.

    observations: list of dicts, keys:
      - ground_station_id: ground station id - int
      - transmitter_uuid: transmitter uuid - str
      - start: observation start - datetime
      - end: observation end - datetime
    """
    # pylint: disable=missing-timeout

    observations_serialized = list(serialize_observation(satpass) for satpass in observations)

    try:
        response = requests.post(f'{settings.NETWORK_BASE_URL}/api/observations/',
                                 json=observations_serialized,
                                 headers={'Authorization': f'Token {settings.SATNOGS_API_TOKEN}'})
        response.raise_for_status()
        logger.debug(f"Scheduled {len(observations_serialized)} passes!")
    except requests.HTTPError:
        err = response.json()
        handle_batch_scheduling_error(err)

        logger.info('Fall-back to single-pass scheduling...')
        for observation in observations:
            schedule_observation(observation)


def schedule_observation(observation):
    """
    Schedule observation in SatNOGS Network.

    observation: dict, keys:
      - ground_station: ground station id - int
      - transmitter_uuid: transmitter uuid - str
      - start: observation start - datetime
      - end: observation end - datetime
    """
    # pylint: disable=missing-timeout

    try:
        response = requests.post(f'{settings.NETWORK_BASE_URL}/api/observations/',
                                 json=[serialize_observation(observation)],
                                 headers={'Authorization': f'Token {settings.SATNOGS_API_TOKEN}'})
        response.raise_for_status()
        logger.info(f"Scheduled pass at {observation['start']:%Y-%m-%dT%H:%M:%S}!")
    except requests.HTTPError:
        err = response.json()
        handle_single_scheduling_error(observation, err)
