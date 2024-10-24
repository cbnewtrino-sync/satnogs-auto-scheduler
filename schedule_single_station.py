#!/usr/bin/env python3

import sys

try:
    from auto_scheduler.cli.schedule_single_station import main
except ImportError:
    print(
        "ERROR: Failed to import auto_scheduler module.\n"
        "Make sure satnogs-auto-scheduler is properly installed.\n"
    )
    sys.exit()


if __name__ == "__main__":
    main()
