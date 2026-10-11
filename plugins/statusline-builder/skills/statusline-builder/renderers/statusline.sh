#!/usr/bin/env bash
# statusline-builder renderer 0.1.0
#
# Draws the active statusline-builder preset from the session JSON on stdin.
# Reads ~/.claude/statusline/config.json ({"active": "<preset>"}) and
# presets/<preset>.json there. Environment overrides, for previews and tests:
#   STATUSLINE_DIR, STATUSLINE_PRESET (a preset file), STATUSLINE_NO_COLOR=1,
#   STATUSLINE_USER, STATUSLINE_HOST, STATUSLINE_HOME, STATUSLINE_NOW (epoch seconds),
#   STATUSLINE_UTC=1 (times in UTC).

input=$(cat)

if ! command -v jq >/dev/null 2>&1; then
    echo "statusline: jq not found"
    exit 0
fi

dir=${STATUSLINE_DIR:-$HOME/.claude/statusline}
preset=${STATUSLINE_PRESET:-}
if [ -z "$preset" ]; then
    active=$(jq -r '.active // empty' "$dir/config.json" 2>/dev/null)
    if [ -z "$active" ]; then
        echo "statusline: no config"
        exit 0
    fi
    preset="$dir/presets/$active.json"
fi
if [ ! -f "$preset" ]; then
    name=$(basename "$preset")
    echo "statusline: preset '${name%.json}' not found"
    exit 0
fi
if ! jq -e '(.lines | type) == "array" and all(.lines[]; type == "array")' "$preset" >/dev/null 2>&1; then
    echo "statusline: invalid preset"
    exit 0
fi

# The input does not carry the git branch, so ask git, only when the preset shows it.
branch=""
if grep -q '"item"[[:space:]]*:[[:space:]]*"branch"' "$preset"; then
    folder=$(jq -r '.workspace.current_dir // .cwd // empty' <<<"$input" 2>/dev/null)
    folder=${folder:-$PWD}
    if [ -d "$folder" ] && command -v git >/dev/null 2>&1; then
        limit=""
        command -v timeout >/dev/null 2>&1 && limit="timeout 1"
        branch=$($limit git -C "$folder" symbolic-ref --short -q HEAD 2>/dev/null) ||
            branch=$($limit git -C "$folder" rev-parse --short HEAD 2>/dev/null) || branch=""
    fi
fi

program='
. as $in |
def kfmt: floor as $n
  | if $n < 1000 then "\($n)"
    else (if $n < 1000000 then [100, "k"] else [100000, "M"] end) as [$div, $unit]
      | (($n / $div) | floor) as $t
      | "\(($t / 10) | floor)" + (if $t % 10 != 0 then ".\($t % 10)" else "" end) + $unit
    end;
def human: floor as $s
  | if $s < 60 then "\($s)s"
    elif $s < 3600 then "\(($s / 60) | floor)m\($s % 60)s"
    else "\(($s / 3600) | floor)h\((($s % 3600) / 60) | floor)m" end;
def money: ((. * 100 + 0.5) | floor) as $c
  | "\(($c / 100) | floor)." + (if $c % 100 < 10 then "0" else "" end) + "\($c % 100)";
def pct: (. + 0.000000001) | floor;
def hhmm: if $utc then gmtime | strftime("%H:%M") else strflocaltime("%H:%M") end;
def isdrive: test("^([A-Za-z]:|\\\\\\\\)");  # a drive or UNC path
def slashes: gsub("\\\\"; "/");
def msys: if test("^/[A-Za-z](/|$)") then (.[1:2] | ascii_upcase) + ":" + .[2:] else . end;
def q: [39] | implode;  # a single quote, which the shell quoting cannot hold
def nonempty: if . == null or . == "" then null else . end;
# Numbers may arrive as strings; anything that is not a number counts as absent.
def num: if type == "number" then . elif type == "string" then (tonumber? // null) else null end;
# Control characters would reach the terminal as escape sequences; drop them.
def clean: tostring | explode | map(select(. >= 32 and . != 127)) | implode;

def folder($seg):
  ($in.workspace.current_dir // $in.cwd // $pwd) as $raw
  | ($raw | isdrive) as $drive
  | (if $drive then $raw | slashes else $raw end) as $p
  | (if $drive then $home | slashes | msys else $home end) as $h0
  | (if ($h0 | length) > 1 then $h0 | sub("/+$"; "") else $h0 end) as $h
  | (if $drive then ($p | ascii_downcase) else $p end) as $pc
  | (if $drive then ($h | ascii_downcase) else $h end) as $hc
  | (if $hc == "" then $p
     elif $pc == $hc then "~"
     elif ($pc | startswith($hc + "/")) then "~" + $p[($h | length):]
     else $p end) as $f
  | (($seg.max | num) // 35 | floor) as $max
  | ([[(($seg.keep | num) // 32 | floor), $max] | min, 0] | max) as $keep
  | ($seg.ellipsis // "..." | tostring) as $ell
  | if ($f | length) > $max then $ell + (if $keep == 0 then "" else $f[(($f | length) - $keep):] end) else $f end;

def usage: $in.context_window.current_usage
  | if . == null then null
    else ((.input_tokens | num) // 0) + ((.cache_creation_input_tokens | num) // 0)
      + ((.cache_read_input_tokens | num) // 0) end;

def limit($w):
  if ($w | type) != "object" or ($w.used_percentage | num) == null then null
  else ($w.used_percentage | num | pct) as $v
    | {value: "\($v)", n: $v,
       resets: ($w.resets_at | num | if . == null then "" else hhmm end),
       usd: ($w.used_usd | num | if . == null then "" else money end),
       limit: ($w.limit_usd | num | if . == null then "" else money end)}
  end;

def text1($v): if ($v | nonempty) == null then null else {value: "\($v)"} end;

# The value and placeholders of one item, or null when it has nothing to show.
def value($id; $seg):
  if $id == "user" then text1($user)
  elif $id == "host" then text1($host)
  elif $id == "folder" then {value: folder($seg)}
  elif $id == "ctx_used" then usage | if . == null then null else {value: "\(floor)", k: kfmt, n: .} end
  elif $id == "ctx_max" then $in.context_window.context_window_size | num
    | if . == null then null else {value: "\(floor)", k: kfmt, n: .} end
  elif $id == "ctx_pct" then $in.context_window.used_percentage | num
    | if . == null then null else pct as $v | {value: "\($v)", n: $v} end
  elif $id == "model" then $in.model.display_name
    | if . == null then null else {value: ., id: ($in.model.id // "")} end
  elif $id == "effort" then text1($in.effort.level)
  elif $id == "fast_mode" then (if $in.fast_mode == true then {value: "fast"} else null end)
  elif $id == "thinking" then (if $in.thinking.enabled == true then {value: "thinking"} else null end)
  elif $id == "output_style" then text1($in.output_style.name)
  elif $id == "vim_mode" then text1($in.vim.mode)
  elif $id == "session_name" then text1($in.session_name)
  elif $id == "cost" then $in.cost.total_cost_usd | num | if . == null then null else {value: money, n: .} end
  elif $id == "duration" then $in.cost.total_duration_ms | num | if . == null then null else {value: (. / 1000 | human)} end
  elif $id == "api_duration" then $in.cost.total_api_duration_ms | num | if . == null then null else {value: (. / 1000 | human)} end
  elif $id == "lines_added" then $in.cost.total_lines_added | num | if . == null then null else {value: "\(.)", n: .} end
  elif $id == "lines_removed" then $in.cost.total_lines_removed | num | if . == null then null else {value: "\(.)", n: .} end
  elif $id == "repo" then $in.workspace.repo
    | if . == null or .name == null then null
      else {value: ((if .owner then .owner + "/" else "" end) + .name),
            owner: (.owner // ""), name: .name, host: (.host // "")} end
  elif $id == "branch" then text1($branch)
  elif $id == "worktree" then text1($in.worktree.name // $in.workspace.git_worktree)
  elif $id == "pr" then $in.pr
    | if . == null or .number == null then null
      else {value: "\(.number)", state: (.review_state // ""), url: (.url // "")} end
  elif $id == "rate_5h" then limit($in.rate_limits.five_hour)
  elif $id == "rate_7d" then limit($in.rate_limits.seven_day)
  elif $id == "spend" then limit($in.rate_limits.spend_limit)
  elif $id == "cache_hit" then $in.prompt_cache.hit_ratio | num
    | if . == null then null else (. * 100 | pct) as $v | {value: "\($v)", n: $v} end
  elif $id == "cache_ttl" then $in.prompt_cache.expires_at | num
    | if . == null or . <= $now then null else {value: (. - $now | human)} end
  else error("unknown item \(q)\($id)\(q)") end;

def defaults: {
  user: "{value}", host: "{value}", folder: "{value}", ctx_used: "{k}", ctx_max: "{k}",
  ctx_pct: "{value}%", model: "{value}", effort: "{value}", fast_mode: "{value}",
  thinking: "{value}", output_style: "{value}", vim_mode: "{value}", session_name: "{value}",
  cost: "${value}", duration: "{value}", api_duration: "{value}", lines_added: "+{value}",
  lines_removed: "-{value}", repo: "{value}", branch: "{value}", worktree: "{value}",
  pr: "PR #{value}", rate_5h: "5h {value}%", rate_7d: "7d {value}%", spend: "{value}%",
  cache_hit: "cache {value}%", cache_ttl: "{value}"
};

def fill($fmt; $r): reduce ($r | to_entries[] | select(.key != "n")) as $e
  ($fmt; split("{" + $e.key + "}") | join($e.value | tostring));

def names: {black: 0, red: 1, green: 2, yellow: 3, blue: 4, magenta: 5, cyan: 6, white: 7};
def hexbyte: ascii_downcase | explode
  | map(if . >= 97 then . - 87 else . - 48 end) | .[0] * 16 + .[1];
def ansi:  # a colour value as SGR parameters
  if . == null then null
  elif type == "number" then "38;5;\(floor)"
  elif type != "string" then null
  elif test("^[0-9]+$") then "38;5;" + .
  elif test("^#[0-9a-fA-F]{6}$") then "38;2;\(.[1:3] | hexbyte);\(.[3:5] | hexbyte);\(.[5:7] | hexbyte)"
  elif startswith("bright_") then names[.[7:]] | if . == null then null else "\(. + 90)" end
  else names[.] | if . == null then null else "\(. + 30)" end end;

def threshold($seg; $n):
  if ($seg.thresholds | type) != "array" or $n == null then $seg.color
  else [$seg.thresholds[] | select(type == "object")
        | select(.below == null or (.below | num) == null or $n < (.below | num))][0].color // $seg.color end;

def styled($raw; $seg; $colour):
  ($raw | clean) as $text
  | ((if $seg.bold == true then ["1"] else [] end) + ([$colour | ansi] | map(select(. != null)))) as $codes
  | if $nocolor or ($codes | length) == 0 or $text == "" then $text
    else "\u001b[" + ($codes | join(";")) + "m" + $text + "\u001b[0m" end;

def render_line:
  [ .[] | select(type == "object") | . as $seg
    | if has("item") then
        (try value($seg.item; $seg) catch null) as $r
        | (if $r == null then "" else (try fill($seg.format // defaults[$seg.item] | tostring; $r) catch "") end) as $t
        | {kind: "item", shown: ($t != ""),
           out: (if $t == "" then "" else styled($t; $seg; threshold($seg; $r.n)) end)}
      elif has("sep") then {kind: "sep", shown: false, out: styled($seg.sep; $seg; $seg.color)}
      else {kind: "text", shown: false, out: styled($seg.text // ""; $seg; $seg.color)} end ] as $s
  | [range(0; $s | length) | select($s[.].shown)] as $items
  | if ($items | length) == 0 then empty
    else
      [range(0; $s | length) as $i | $s[$i]
       | if .kind != "sep" then .out
         else ([$items[] | select(. < $i)] | last) as $prev
           | ([$items[] | select(. > $i)] | first) as $next
           | if $prev == null or $next == null then ""
             elif ([range($prev + 1; $i) | select($s[.].kind == "sep")] | length) > 0 then ""
             else .out end
         end] | join("")
    end;

$preset[0] as $p
| [$p.lines[][] | select(type == "object" and has("item"))
   | select((.item | type) != "string" or defaults[.item] == null) | (.item // "" | tostring)] as $bad
| if ($bad | length) > 0 then "statusline: unknown item \(q)\($bad[0])\(q)"
  else $p.lines[] | render_line end
'

user=${STATUSLINE_USER:-$(id -un 2>/dev/null || whoami)}
host=${STATUSLINE_HOST:-$(hostname -s 2>/dev/null || hostname)}
home=${STATUSLINE_HOME:-$HOME}
now=${STATUSLINE_NOW:-$(date +%s)}
nocolor=false
[ "${STATUSLINE_NO_COLOR:-0}" = 1 ] && nocolor=true
utc=false
[ "${STATUSLINE_UTC:-0}" = 1 ] && utc=true

if ! out=$(jq -r \
    --slurpfile preset "$preset" \
    --arg user "$user" --arg host "$host" --arg home "$home" --arg pwd "$PWD" \
    --arg branch "$branch" --argjson now "$now" \
    --argjson nocolor "$nocolor" --argjson utc "$utc" \
    "$program" <<<"$input" 2>"${STATUSLINE_DEBUG:-/dev/null}"); then
    echo "statusline: invalid input"
    exit 0
fi
[ -n "$out" ] && printf '%s\n' "$out"
exit 0
