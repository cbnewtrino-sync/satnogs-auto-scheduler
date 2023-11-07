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


def validate_config_exists():
    search_path = config._caller_path()  # pylint: disable=protected-access
    filename = config._find_file(search_path)  # pylint: disable=protected-access
    if filename == '':
        print(f"ERROR: No configuration file found at {search_path}/\n"
              "Run the following command to generate it: \n"
              "satnogs_auto_scheduler_setup.py")
        sys.exit(1)


def validate_token(token, token_name):
    # Define a regular expression pattern for the SatNOGS [Network|DB] API Tokens
    pattern = r"^[a-f0-9]{40}$"

    valid = bool(re.match(pattern, token))

    if not valid:
        print(f"ERROR: Invalid value for {token_name} in configuration file.\n"
              "The API Token should be exactly 40 characters long "
              "and consists of lowercase letters 'a' to 'f' and digits '0' to '9'.")
        print("Please double-check the API Token you provided.")
        sys.exit(1)


def validate_loaded_config():
    validate_token(SATNOGS_API_TOKEN, token_name='SATNOGS_API_TOKEN')
    validate_token(SATNOGS_DB_API_TOKEN, token_name='SATNOGS_DB_API_TOKEN')


def validate_config():
    validate_config_exists()
    validate_loaded_config()
