#!/bin/bash
# One load run with ApacheBench (ab): bench.sh LABEL URL PID [COOKIE]
#   50 concurrent connections, keep-alive, 30 s, after a 5 s warm-up. Prints requests per second,
#   the latency percentiles, the server's CPU seconds and resident memory (PID is the server process).
# Pin the servers and the load generator to different CPUs (taskset) for a comparable run.
label=$1; url=$2; pid=$3; cookie=$4
args=(-k -q -n 10000000)
[ -n "$cookie" ] && args+=(-C "$cookie")
ab "${args[@]}" -c 10 -t 5 "$url" >/dev/null 2>&1
cpu() { awk '{print ($14+$15)/100}' /proc/$pid/stat; }
c0=$(cpu)
out=$(ab "${args[@]}" -c 50 -t 30 "$url" 2>&1)
c1=$(cpu)
echo "$label: rps=$(echo "$out" | awk '/Requests per second/ {print $4}') failed=$(echo "$out" | awk '/Failed requests/ {print $3}') cpu_s=$(python3 -c "print(round($c1-$c0,1))") rss_kb=$(awk '/VmRSS/ {print $2}' /proc/$pid/status)"
echo "$out" | awk '/Percentage of the requests/ {p=1} p' | grep -E "50%|95%|99%|100%" | tr -s ' ' | tr '\n' ' '; echo
