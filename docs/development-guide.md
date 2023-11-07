# Development Guide

## Installation

For development, clone the source reposistory and create an editable installation of the
auto-scheduler, the installation of extra development dependencies (e.g. linters).

```
git clone https://gitlab.com/librespacefoundation/satnogs/satnogs-auto-scheduler
cd satnogs-auto-scheduler
mkvirtualenv auto-scheduler
pip install -e '.[dev]'
```

## Run static code analyis

The following command can be used to run all static code analysis tools on all files:
```
pre-commit run --all-files
```
