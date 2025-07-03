# auto-scheduler

This is a tool to automatically compute passes of satellites and schedule observations on the
[SatNOGS Network](https://network.satnogs.org/). It is based on the scheduling code from
SatNOGS network and requires [python-satellitetle](https://gitlab.com/librespacefoundation/python-satellitetle) for downloading TLEs.


## Installation

(tested with Linux / Debian)

Ensure git and Python is installed, and create a directory for all upcoming files.
Then create a Python virtual environment, activate it and install the desired
version of satnogs-auto-scheduler with pip directly from the remote git repository.

```bash
sudo apt-get update
sudo apt-get -y install git python3

mkdir auto-scheduler
cd auto-scheduler
python3 -m venv .venv
source .venv/bin/activate
pip install git+https://gitlab.com/librespacefoundation/satnogs/satnogs-auto-scheduler.git@0.4
```

Verify the installation by checking the installed version:
```
$ schedule_single_station --version
satnogs-auto-scheduler 0.4
```

NOTE: Previous releases of this guide installed the virtual environment in a directory called `env`.
This has been changed to `.venv` to follow the official [Python Packaging User Guide on virtual environments](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/#create-and-use-virtual-environments).

## Usage

### Current command (supported for now):

```
schedule_single_station.py [options]
./schedule_single_station.py [options]  # Legacy method, works but may be missing version info
```

### New command (preferred):

```
schedule_single_station [options]
```

## Configuration

Run the following script:
```
satnogs_auto_scheduler_setup
```

Follow the prompts to enter your SatNOGS DB and Network API tokens, The configuration file `.env` is generated.

NOTE: Since auto-scheduler version {unreleased} both SatNOGS Network & DB API Tokens are required!

## Test run

Perform a test run to download orbital elements and transmitter priorities (these are stored in `/tmp/cache`) with

```bash
schedule_single_station -s <ground station ID> -n
```

The `-n` option computes the passes but does not schedule them. To schedule these passes, run

```bash
schedule_single_station -s <ground station ID>
```

## Setup priority scheduling

The script `contrib/gen_prio_file.sh` can be used to generate a list of transmitters for prioritization, selecting
all DUV, BPSK1k2, BPSK9k6, [G]MSK and [G]FSK transmitters. To create the file `priorities_37.txt`, run
```
schedule_single_station --station 37 -n
contrib/gen_prio_file.sh 37 > priorities_37.txt
```

Please change the station id (here `37`) to your corresponding one!

## Automation
### Add cron-job (Option A)

Start editing your default user's cron (select your preferred editor):
```bash
crontab -e
```

Add a line like this - execute the scheduling script on each full hour:
```bash
0 */1 * * * <path_to_auto_scheduler>/.venv/bin/schedule_single_station -s <station_id> -d 1.2 -P <path_to_priority_list>/<priority_file>.txt -f -z
```

Omit the `-f` option to also fill in the gaps, but be aware if using a rotator setup! This will wear-out your rotator very quickly!
Add `-w 60` for a delay if you want to give your rotator a bit of time (60 s) to reset or home.

### Add systemd-timer (Option B)
The advantage of using a systemd-timer for invoking the auto-scheduler lies in the better logging output (you can use `journalctl -u satnogs-auto-scheduler.service` to access the log output).

- Add a systemd service unit file at `/etc/systemd/system/satnogs-auto-scheduler.service`:
   ```
   [Unit]
   Description=Schedule SatNOGS observations for 1.2h on station 132

   [Service]
   Type=oneshot
   ExecStart=<path_to_auto_scheduler>/.venv/bin/schedule_single_station -s <station_id> -d 1.2 -P <path_to_priority_list>/<priority_file>.txt -z
   User=pi
   ```

- Add a systemd timer unit file at `/etc/systemd/system/satnogs-auto-scheduler.timer`:
  ```
  [Unit]
  Description=Run satnogs-auto-scheduler hourly and on boot

  [Timer]
  OnBootSec=2min
  OnUnitActiveSec=1h

  [Install]
  WantedBy=timers.target
  ```

- Start the timer with
  ```bash
  sudo systemctl start satnogs-auto-scheduler.timer
  ```

- Enable the timer to be started on boot with
  ```bash
  sudo systemctl enable satnogs-auto-scheduler.timer
  ```

If you want to run the auto-scheduler once manually, you can do so with
```bash
sudo systemctl start satnogs-auto-scheduler.service
```

## Usage

The following command will list all available command-line arguments:
```bash
schedule_single_station --help
```

## License
[![license](https://img.shields.io/badge/license-AGPL%203.0-6672D8.svg)](LICENSE)
Copyright 2019 - Cees Bassa, Fabian Schmidt, Pierros Papadeas
