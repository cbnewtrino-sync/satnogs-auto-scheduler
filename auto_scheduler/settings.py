import re
import sys
from pathlib import Path
from tempfile import gettempdir

from decouple import config

# Basic settings
DB_BASE_URL = config('DB_BASE_URL', default='https://db.satnogs.org')
NETWORK_BASE_URL = config('NETWORK_BASE_URL', default='https://network.satnogs.org')
CACHE_DIR = config('CACHE_DIR', default=str(Path(gettempdir(), 'cache')))
CACHE_AGE = config('CACHE_AGE', default=24, cast=float)  # In hours
MIN_PASS_DURATION = config('MIN_PASS_DURATION', default=3, cast=float)  # In minutes

# Credentials
SATNOGS_API_TOKEN = config('SATNOGS_API_TOKEN', default='')
SATNOGS_DB_API_TOKEN = config('SATNOGS_DB_API_TOKEN', default='')


def resolve_config_filename():
    """
    Returns filename as absolute path of the config file which was loaded by python-decouple.

    Returns '/' if no config file was found.
    """
    search_path = config._caller_path()  # pylint: disable=protected-access
    return config._find_file(search_path)  # pylint: disable=protected-access


def resolve_config_path():
    """
    Returns the absolute path where python-decouple searches for the configuraiton file.
    """
    return config._caller_path()  # pylint: disable=protected-access


def validate_token(token, token_name):

    def fail():
        filename = resolve_config_filename()
        print(f"Please double-check your configuration in {filename}")
        sys.exit(1)

    if SATNOGS_API_TOKEN == '':
        print("ERROR: No value for SATNOGS_API_TOKEN in configuration file.")
        fail()

    if SATNOGS_DB_API_TOKEN == '':
        print("ERROR: No value for SATNOGS_DB_API_TOKEN in configuration file.")
        fail()

    # Define a regular expression pattern for the SatNOGS [Network|DB] API Tokens
    pattern = r"^[a-f0-9]{40}$"
    if not bool(re.match(pattern, token)):
        print(f"ERROR: Invalid value for {token_name} in configuration file.\n"
              "The API Token should be exactly 40 characters long "
              "and consists of lowercase letters 'a' to 'f' and digits '0' to '9'.")
        fail()


def validate_loaded_config():
    validate_token(SATNOGS_API_TOKEN, token_name='SATNOGS_API_TOKEN')
    validate_token(SATNOGS_DB_API_TOKEN, token_name='SATNOGS_DB_API_TOKEN')


def validate_config():
    validate_loaded_config()
