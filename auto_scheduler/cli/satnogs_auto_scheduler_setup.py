#!/usr/bin/env python3
"""
SatNOGS Auto-Scheduler Configuration Setup tool

This command-line utility streamlines the configuration of the SatNOGS auto-scheduler
by guiding users through the process of obtaining and entering the required API tokens,
ultimately generating the configuration file.
"""

import os
import re
import sys
from dataclasses import dataclass


@dataclass
class AutoSchedulerConfig:
    db_api_token: str
    network_api_token: str


def validate_token(token):
    # Define a regular expression pattern for the SatNOGS [Network|DB] API Tokens
    pattern = r"^[a-f0-9]{40}$"

    valid = bool(re.match(pattern, token))

    if not valid:
        print(
            "ERROR: The API Token should be exactly 40 characters long "
            "and consists of lowercase letters 'a' to 'f' and digits '0' to '9'."
        )
        print("Please double-check the API Token you provided.")
        sys.exit(1)


def get_tokens():
    """
    Ask the user for the SatNOGS Network and DB API Tokens.
    """
    print("Initializing SatNOGS auto-scheduler config...\n")

    print("==== DB API Token ====")
    print(
        "Login to https://db.satnogs.org/ and click on your profile picture \n"
        "in the top right corner to get to 'Settings / API Token'. \n"
    )

    db_api_token = input("Please enter your API Token for SatNOGS DB: ")
    validate_token(db_api_token)

    print("\n")
    print("==== Network API Token ====")
    print(
        "Log in to https://network.satnogs.org/ and click on the user icon at \n"
        "the top right corner and then click on the 'Dashboard' option. \n"
        "On the top of the dashboard page right under the user icon click the \n"
        "button 'API key' to show your API token. \n"
    )
    network_api_token = input("Please enter your API Token for SatNOGS Network: ")
    validate_token(network_api_token)

    return AutoSchedulerConfig(network_api_token=network_api_token, db_api_token=db_api_token)


def write_env_file(config, filename=".env"):
    if os.path.isfile(filename):
        overwrite = (
            input(f"A file {filename} already exists. Do you want to overwrite it? (Y/n): ")
            .strip()
            .lower()
        )
        if overwrite not in ["y", "yes"]:
            print("Configuration was not written. Exiting.")
            sys.exit()
    try:
        with open(filename, "w") as f_env:
            f_env.write("# Your SatNOGS Network API token\n")
            f_env.write(f"SATNOGS_API_TOKEN = '{config.network_api_token}'\n")
            f_env.write("\n")
            f_env.write("# Your SatNOGS DB API token\n")
            f_env.write(f"SATNOGS_DB_API_TOKEN = '{config.db_api_token}'\n")
            f_env.write("\n")
            path = f_env.name
    except (IOError, OSError) as err:
        print(f"An error occured while writing the configuration: {str(err)}")

    print(f"Configuration has been successfully written to: {os.path.realpath(path)}")


def main():
    new_config = get_tokens()
    write_env_file(new_config)


if __name__ == "__main__":
    main()
