#!/usr/bin/env python3
"""Explain why a satellite's transmitters do or don't reach pass prediction.

Usage: why_not_scheduled.py <station_id> <norad_id> [priorities_file]
Reads the auto-scheduler cache only (no network).
"""
import json
import os
import sys
from datetime import datetime

from auto_scheduler import settings
from auto_scheduler.io import read_priorities_transmitters

station, norad = sys.argv[1], int(sys.argv[2])
prio_file = sys.argv[3] if len(sys.argv) > 3 else None
d = settings.CACHE_DIR
print(f"cache dir: {d}")


def load(name):
    p = os.path.join(d, name)
    age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(p))
    print(f"  {name}: {age.total_seconds() / 3600:.1f} h old")
    with open(p) as fp:
        return json.load(fp)


sats = {int(k): v for k, v in load("satellites.json").items()}
sats2 = load("satellites2.json")
recv = load(f"transmitters_{station}.json")
stats = load("transmitters_stats.json")
tles = load("tles.json")

print(f"\nSatellite {norad}:")
if norad in sats:
    s = sats[norad]
    print(f"  in orbit, name={s.get('name')}, sat_id={s.get('sat_id')}, "
          f"is_frequency_violator={s.get('is_frequency_violator')}")
else:
    hits = [v for v in sats2["satellites"].values() if v.get("norad_cat_id") == norad]
    print("  NOT in alive list" + (f" (status={hits[0].get('status')})" if hits else
                                   " and not in satellites2 at all"))
    for v in sats2["satellites"].values():
        if "ORIGAMI" in str(v.get("name", "")).upper() or v.get("norad_follow_id") == norad:
            print(f"  related: {v.get('name')} norad={v.get('norad_cat_id')} "
                  f"follow={v.get('norad_follow_id')} status={v.get('status')}")

print(f"  TLE in cache: {any(t['norad_cat_id'] == norad for t in tles)}")

fav = {}
if prio_file:
    prios, fav = read_priorities_transmitters(prio_file)
    print(f"\nPriorities file: {prios.get(str(norad))=} favourite={fav.get(str(norad))!r}")

print(f"\nTransmitters receivable at station {station} for {norad}:")
mine = {u: t for u, t in recv.items() if t["norad_cat_id"] == norad}
if not mine:
    print("  none (outside antenna range, or not active in DB)")
for u, t in mine.items():
    st = stats.get(u)
    flag = " <- favourite" if fav.get(str(norad)) == u else ""
    if st is None:
        st_txt = "MISSING (skipped silently)"
    else:
        st_txt = "%s%% good %s/%s" % (st["success_rate"], st["good_count"], st["total_count"])
    print(f"  {u} {t.get('description')!r} mode={t.get('mode')} stats={st_txt}{flag}")
if fav.get(str(norad)) and fav[str(norad)] not in mine:
    print(f"  !! favourite uuid {fav[str(norad)]} is not among these")
