# Changelog

## unreleased

### Breaking Changes
- Moved scripts (`schedule_single_station.py`) into the `auto_scheduler` package. The auto-scheduler must be installed now, running
  `./schedule_single_station.py` will not work anymore. This change is motivated by consolidating all code in the `auto_scheduler` package.
  Recommendation:
  - Install [pipx](https://pipx.pypa.io/stable/installation/)
  - Install the auto-scheduler (pipx will create and use an isolated environment, no manual handling of environments necessary anymore):
    ```
    $ pipx install git+https://gitlab.com/librespacefoundation/satnogs/satnogs-auto-scheduler.git
      installed package satnogs-auto-scheduler 0.3.2.dev30+g6dd23ae, installed using Python 3.12.6
      These apps are now globally available
        - satnogs_auto_scheduler_setup
        - schedule_single_station
    done! ✨ 🌟 ✨
    ```
  - Run the auto-scheduler:
    ```
    $ schedule_single_station --version
    satnogs-auto-scheduler 0.3.2.dev30+g6dd23ae
    ```

### Fixes
- Fixed  scheduling API error handling code, no `AttributeError` on 404 Client errors anymore
  ([ee5babe](https://gitlab.com/librespacefoundation/satnogs/satnogs-auto-scheduler/-/commit/ee5babee46e221684a966da8ad6ac04a836b3d8d)))
- Fixed version info display to be available even if the use configuration is currently invalid
- Fixed stdout cluttering with progress bars in non-interactive terminals

### Other Changes
- Updated Python from 3.8 to 3.11
- Fixed version information when running in docker container
- Simplified Dockerfile
- Modernized packaging: Introduced `pyproject.toml`, change build backend to `hatchling'
- Removed vendorized `versioneer` package. This functionality is provided by the new build backend [Hatch](https://hatch.pypa.io/) now
- Changed linter/formatter to ruff; this made all these previously used tools obsolete: flake8, isort, yapf and pylint
- Changed CI to use the LSF gitlab-ci templates. This way maintainance of the CI is shared with other LSF projects
- Enabled GitLab [Code Quality](https://docs.gitlab.com/ee/ci/testing/code_quality.html), linter/formatter errors will be shown in
  Merge Requests now

## 0.3.1 - 2023-11-08

- Removed broken check if the configuration file exists,
  fixes config via env variables (e.g. when using docker)
- Added short developement guide at <docs/development-guide.md>
- Changed error message if API Token is invalid

## 0.3 - 2023-11-04

### Breaking Changes

The SatNOGS DB API Token is always required now. Thus TLEs are fetched from SatNOGS DB diretly
which has multiple benefits. It is much faster than the old method, removes errors when a satellite
entry is using TLEs produced by "new" sources (e.g. SatNOGS Team) and enables output improvements.

### Changes (non exhaustive list)

- Added station-agnostic caching of SatNOGS Netowork transmitter statistics and the SatNOGS DB
  satellite information. Allows re-using the transmitter statistics when sequentially scheduling
  multiple stations. The cache age is determined by the modification timestamp (mtime) in the filesystem.
- Added the usage of satellite names from SatNOGS DB in log output.
- Removed scheduling for satellites with the "frequency misuse" flag in SatNOGS DB.
  Unless the user had special SSA permissions those passes were not scheduled already but made the
  batch-scheduling fail often times. This change follows the
  [change](https://community.libre.space/t/changes-in-network-and-db-for-satellites-that-violate-frequency-regulations/9395)
  in SatNOGS for satellites that violate frequency regulations.
- Removed the deprecated method of fetching TLEs from various sources,
  always fetch TLEs from SatNOGS DB now.
- Enabled scheduling for satellites with temporary NORAD ID (>90000). This makes it obsolete to filter for
  satellite with a maximum norad id.
- Removed the `MAX_NROAD_CAT_ID` setting.
- Added `satnogs_auto_scheduler_setup.py` helper script.
- Added input validation for API Tokens from config.
- Improved log output for scheduling errors.

## 0.2 - 2023-02-06 - 2b77522

First release in 2023.

## v0.1 - 2018-12-02 - 1a844c7

Initial stable release.
