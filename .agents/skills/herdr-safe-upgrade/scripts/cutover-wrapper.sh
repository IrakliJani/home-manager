#!/bin/zsh
set -eu

if (( $# < 2 || $# > 3 )); then
    print -u2 "usage: $0 <launchd-label> <migration-bundle> [delay-seconds]"
    exit 64
fi

label=$1
bundle=${2:A}
delay=${3:-15}
config="$bundle/migration-config.json"
engine="$bundle/herdr_migrate.py"
log_file="$bundle/cutover.log"

if [[ ! -f $config || ! -x $engine ]]; then
    print -u2 "invalid migration bundle: $bundle"
    exit 66
fi

# launchctl submit jobs restart after a normal exit. Remove this job before the
# wrapper exits so a completed cutover cannot be retried indefinitely.
cleanup() {
    trap - EXIT INT TERM
    launchctl remove "$label" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

export HOME=$(/usr/bin/python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["home"])' "$config")
export PATH=$(/usr/bin/python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["path"])' "$config")

exec >>"$log_file" 2>&1
printf '[%s] detached cutover scheduled; waiting %s seconds\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$delay"
sleep "$delay"
/usr/bin/python3 "$engine" cutover
