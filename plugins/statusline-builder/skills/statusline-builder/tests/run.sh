#!/usr/bin/env bash
# Runs both renderers over every preset and fixture that has an expected output, and
# checks that each renderer handles every catalog item. Exits non-zero on any failure.
#
#   tests/run.sh            bash renderer, plus PowerShell when one is found
#   tests/run.sh bash       bash renderer only
#   tests/run.sh powershell PowerShell renderer only
#
# PowerShell is `pwsh` when on PATH, else Windows PowerShell through WSL's powershell.exe.
set -u

here=$(cd "$(dirname "$0")" && pwd)
root=$(dirname "$here")
only=${1:-}

pass=0
fail=0

ps_cmd=""
if command -v pwsh >/dev/null 2>&1; then
    ps_cmd=pwsh
elif command -v powershell.exe >/dev/null 2>&1; then
    ps_cmd=powershell.exe
fi

# Paths as the PowerShell process sees them.
ps_path() {
    if [ "$ps_cmd" = powershell.exe ]; then wslpath -w "$1"; else printf '%s' "$1"; fi
}

# run_renderer <bash|powershell> <preset file> <fixture file> <colour 0|1>
run_renderer() {
    local kind=$1 preset=$2 fixture=$3 colour=$4 home=/home/sean
    case "$(basename "$fixture")" in windows_*) home='C:\Users\sean' ;; esac
    local nocolor=1
    [ "$colour" = 1 ] && nocolor=0
    if [ "$kind" = bash ]; then
        STATUSLINE_PRESET=$preset STATUSLINE_NO_COLOR=$nocolor STATUSLINE_USER=sean \
        STATUSLINE_HOST=box STATUSLINE_HOME=$home STATUSLINE_NOW=1738425000 STATUSLINE_UTC=1 \
            bash "$root/renderers/statusline.sh" < "$fixture"
    else
        STATUSLINE_PRESET=$(ps_path "$preset") STATUSLINE_NO_COLOR=$nocolor STATUSLINE_USER=sean \
        STATUSLINE_HOST=box STATUSLINE_HOME=$home STATUSLINE_NOW=1738425000 STATUSLINE_UTC=1 \
        WSLENV=STATUSLINE_PRESET:STATUSLINE_NO_COLOR:STATUSLINE_USER:STATUSLINE_HOST:STATUSLINE_HOME:STATUSLINE_NOW:STATUSLINE_UTC \
            "$ps_cmd" -NoProfile -ExecutionPolicy Bypass -File "$(ps_path "$root/renderers/statusline.ps1")" < "$fixture"
    fi
}

check() {
    local kind=$1 preset=$2 fixture=$3 expected=$4 colour=$5 name
    name="$kind $(basename "$expected")"
    local actual
    actual=$(run_renderer "$kind" "$preset" "$fixture" "$colour"; printf x)
    actual=${actual%x}
    local want
    want=$(cat "$expected"; printf x)
    want=${want%x}
    if [ "$actual" = "$want" ]; then
        pass=$((pass + 1))
    else
        fail=$((fail + 1))
        echo "FAIL $name"
        diff <(printf '%s' "$want" | cat -v) <(printf '%s' "$actual" | cat -v) | sed 's/^/    /'
    fi
}

kinds=()
[ "$only" != powershell ] && kinds+=(bash)
if [ "$only" != bash ]; then
    if [ -n "$ps_cmd" ]; then kinds+=(powershell); else echo "SKIP powershell: no pwsh or powershell.exe"; fi
fi

for kind in "${kinds[@]}"; do
    for expected in "$here"/expected/*.txt "$here"/expected/*.color; do
        [ -e "$expected" ] || continue
        base=$(basename "$expected")
        stem=${base%.*}
        preset_name=${stem%%__*}
        fixture_name=${stem#*__}
        preset="$root/presets/$preset_name.json"
        [ -f "$preset" ] || preset="$here/presets/$preset_name.json"
        colour=0
        [ "${base##*.}" = color ] && colour=1
        check "$kind" "$preset" "$here/fixtures/$fixture_name.json" "$expected" "$colour"
    done
done

# Every catalog item must be handled by both renderers.
for id in $(jq -r '.items[].id' "$root/catalog.json"); do
    for r in statusline.sh statusline.ps1; do
        if [ -f "$root/renderers/$r" ] && grep -q "'$id'\|\"$id\"" "$root/renderers/$r"; then
            pass=$((pass + 1))
        else
            fail=$((fail + 1))
            echo "FAIL $r does not handle item '$id'"
        fi
    done
done

echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
