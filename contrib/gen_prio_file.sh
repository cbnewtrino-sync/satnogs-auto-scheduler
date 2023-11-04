#!/bin/bash
#
# Usage:
# gen_prio_file.sh 37 > priorities_37.txt"

STATION_ID=$1
TRM_FILE="/tmp/cache/transmitters_${STATION_ID}.txt"

awk '{if ($3>=80) print $0 }' ${TRM_FILE} | grep -e "FSK" | awk '{printf("%s 1.0 %s\n",$1,$2)}'
awk '{if ($3>=0) print $0 }' ${TRM_FILE} | grep -e "BPSK1k2" | awk '{printf("%s 1.0 %s\n",$1,$2)}'
awk '{if ($3>=0) print $0 }' ${TRM_FILE} | grep -e "BPSK9k6" | awk '{printf("%s 1.0 %s\n",$1,$2)}'
awk '{if ($3>=80) print $0 }' ${TRM_FILE} | grep -e "MSK" | awk '{printf("%s 1.0 %s\n",$1,$2)}'
sort -n -k 4 ${TRM_FILE} | grep -e "DUV" | awk '{printf("%s 1.0 %s\n",$1,$2)}'
