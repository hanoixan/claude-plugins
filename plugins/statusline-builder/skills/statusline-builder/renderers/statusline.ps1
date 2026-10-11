# statusline-builder renderer 0.1.0
#
# Draws the active statusline-builder preset from the session JSON on stdin.
# Reads ~/.claude/statusline/config.json ({"active": "<preset>"}) and
# presets/<preset>.json there. Environment overrides, for previews and tests:
#   STATUSLINE_DIR, STATUSLINE_PRESET (a preset file), STATUSLINE_NO_COLOR=1,
#   STATUSLINE_USER, STATUSLINE_HOST, STATUSLINE_HOME, STATUSLINE_NOW (epoch seconds),
#   STATUSLINE_UTC=1 (times in UTC).
# Written for Windows PowerShell 5.1 and PowerShell 7 alike.

$utf8 = New-Object System.Text.UTF8Encoding $false
$esc = [string][char]27
$quote = [string][char]39

function Write-Output-Text([string]$text) {
    $stream = [Console]::OpenStandardOutput()
    $bytes = $utf8.GetBytes($text)
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Flush()
}

function Stop-With([string]$message) {
    Write-Output-Text ("statusline: " + $message + "`n")
    exit 0
}

function Test-Has($object, [string]$name) {
    return ($null -ne $object) -and ($null -ne $object.PSObject.Properties[$name])
}

# Lower-cases A to Z only, as jq's ascii_downcase does.
function ConvertTo-AsciiLower([string]$text) {
    $chars = $text.ToCharArray()
    for ($i = 0; $i -lt $chars.Length; $i++) {
        if (($chars[$i] -ge 'A') -and ($chars[$i] -le 'Z')) { $chars[$i] = [char]([int]$chars[$i] + 32) }
    }
    return -join $chars
}

function Test-Empty($value) {
    return ($null -eq $value) -or ([string]$value -eq '')
}

function Format-K($number) {
    $n = [long][Math]::Floor([double]$number)
    if ($n -lt 1000) { return [string]$n }
    if ($n -lt 1000000) { $div = 100; $unit = 'k' } else { $div = 100000; $unit = 'M' }
    $t = [long][Math]::Floor($n / $div)
    $text = [string][long][Math]::Floor($t / 10)
    if (($t % 10) -ne 0) { $text += '.' + [string]($t % 10) }
    return $text + $unit
}

function Format-Human($seconds) {
    $s = [long][Math]::Floor([double]$seconds)
    if ($s -lt 60) { return "${s}s" }
    if ($s -lt 3600) { return ([string][long][Math]::Floor($s / 60)) + 'm' + ([string]($s % 60)) + 's' }
    return ([string][long][Math]::Floor($s / 3600)) + 'h' + ([string][long][Math]::Floor(($s % 3600) / 60)) + 'm'
}

function Format-Money($amount) {
    $c = [long][Math]::Floor([double]$amount * 100 + 0.5)
    $cents = [string]($c % 100)
    if ($cents.Length -lt 2) { $cents = '0' + $cents }
    return ([string][long][Math]::Floor($c / 100)) + '.' + $cents
}

function Get-Pct($value) {
    return [long][Math]::Floor([double]$value + 0.000000001)
}

function Format-Time($epoch) {
    $moment = [DateTimeOffset]::FromUnixTimeSeconds([long][Math]::Floor([double]$epoch))
    if ($script:utc) { $when = $moment.UtcDateTime } else { $when = $moment.LocalDateTime }
    return $when.ToString('HH:mm', [Globalization.CultureInfo]::InvariantCulture)
}

function Get-Folder($seg) {
    $raw = $script:data.workspace.current_dir
    if (Test-Empty $raw) { $raw = $script:data.cwd }
    if (Test-Empty $raw) { $raw = (Get-Location).Path }
    $raw = [string]$raw
    $drive = $raw -match '^([A-Za-z]:|\\\\)'  # a drive or UNC path
    $p = $raw
    $h = [string]$script:homeDir
    if ($drive) {
        $p = $p.Replace('\', '/')
        $h = $h.Replace('\', '/')
        if ($h -match '^/[A-Za-z](/|$)') { $h = $h.Substring(1, 1).ToUpperInvariant() + ':' + $h.Substring(2) }
    }
    if ($h.Length -gt 1) { $h = $h -replace '/+$', '' }
    $pc = $p; $hc = $h
    if ($drive) { $pc = ConvertTo-AsciiLower $p; $hc = ConvertTo-AsciiLower $h }
    if ($hc -eq '') { $f = $p }
    elseif ($pc -eq $hc) { $f = '~' }
    elseif ($pc.StartsWith($hc + '/', [StringComparison]::Ordinal)) { $f = '~' + $p.Substring($h.Length) }
    else { $f = $p }
    $max = 35; $keep = 32; $ellipsis = '...'
    try { if (Test-Has $seg 'max') { $max = [int][Math]::Floor([double]$seg.max) } } catch { }
    try { if (Test-Has $seg 'keep') { $keep = [int][Math]::Floor([double]$seg.keep) } } catch { }
    if (Test-Has $seg 'ellipsis') { $ellipsis = [string]$seg.ellipsis }
    $keep = [Math]::Max([Math]::Min($keep, $max), 0)
    if ($f.Length -gt $max) { $f = $ellipsis + $f.Substring($f.Length - $keep) }
    return $f
}

function Get-Limit($window) {
    if (($null -eq $window) -or ($null -eq $window.used_percentage)) { return $null }
    $v = Get-Pct $window.used_percentage
    $r = [ordered]@{ value = [string]$v; n = $v; resets = ''; usd = ''; limit = '' }
    if ($null -ne $window.resets_at) { $r.resets = Format-Time $window.resets_at }
    if ($null -ne $window.used_usd) { $r.usd = Format-Money $window.used_usd }
    if ($null -ne $window.limit_usd) { $r.limit = Format-Money $window.limit_usd }
    return $r
}

function New-Text($value) {
    if (Test-Empty $value) { return $null }
    return [ordered]@{ value = [string]$value }
}

# The value and placeholders of one item, or $null when it has nothing to show.
function Get-Value([string]$id, $seg) {
    $d = $script:data
    switch ($id) {
        'user' { return New-Text $script:user }
        'host' { return New-Text $script:hostName }
        'folder' { return [ordered]@{ value = (Get-Folder $seg) } }
        'ctx_used' {
            $u = $d.context_window.current_usage
            if ($null -eq $u) { return $null }
            $t = 0.0
            foreach ($k in 'input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens') {
                if ($null -ne $u.$k) { $t += [double]$u.$k }
            }
            return [ordered]@{ value = [string][long][Math]::Floor($t); k = (Format-K $t); n = $t }
        }
        'ctx_max' {
            $m = $d.context_window.context_window_size
            if ($null -eq $m) { return $null }
            return [ordered]@{ value = [string][long][Math]::Floor([double]$m); k = (Format-K $m); n = [double]$m }
        }
        'ctx_pct' {
            $v = $d.context_window.used_percentage
            if ($null -eq $v) { return $null }
            $v = Get-Pct $v
            return [ordered]@{ value = [string]$v; n = $v }
        }
        'model' {
            $name = $d.model.display_name
            if ($null -eq $name) { return $null }
            $modelId = ''
            if ($null -ne $d.model.id) { $modelId = [string]$d.model.id }
            return [ordered]@{ value = [string]$name; id = $modelId }
        }
        'effort' { return New-Text $d.effort.level }
        'fast_mode' { if ($d.fast_mode -eq $true) { return [ordered]@{ value = 'fast' } } else { return $null } }
        'thinking' { if ($d.thinking.enabled -eq $true) { return [ordered]@{ value = 'thinking' } } else { return $null } }
        'output_style' { return New-Text $d.output_style.name }
        'vim_mode' { return New-Text $d.vim.mode }
        'session_name' { return New-Text $d.session_name }
        'cost' {
            $c = $d.cost.total_cost_usd
            if ($null -eq $c) { return $null }
            return [ordered]@{ value = (Format-Money $c); n = [double]$c }
        }
        'duration' {
            $ms = $d.cost.total_duration_ms
            if ($null -eq $ms) { return $null }
            return [ordered]@{ value = (Format-Human ([double]$ms / 1000)) }
        }
        'api_duration' {
            $ms = $d.cost.total_api_duration_ms
            if ($null -eq $ms) { return $null }
            return [ordered]@{ value = (Format-Human ([double]$ms / 1000)) }
        }
        'lines_added' {
            $v = $d.cost.total_lines_added
            if ($null -eq $v) { return $null }
            return [ordered]@{ value = [string]$v; n = [double]$v }
        }
        'lines_removed' {
            $v = $d.cost.total_lines_removed
            if ($null -eq $v) { return $null }
            return [ordered]@{ value = [string]$v; n = [double]$v }
        }
        'repo' {
            $r = $d.workspace.repo
            if (($null -eq $r) -or ($null -eq $r.name)) { return $null }
            $owner = ''; $repoHost = ''
            if ($null -ne $r.owner) { $owner = [string]$r.owner }
            if ($null -ne $r.host) { $repoHost = [string]$r.host }
            $v = [string]$r.name
            if ($owner -ne '') { $v = $owner + '/' + $v }
            return [ordered]@{ value = $v; owner = $owner; name = [string]$r.name; host = $repoHost }
        }
        'branch' { return New-Text $script:branch }
        'worktree' {
            $w = $d.worktree.name
            if (Test-Empty $w) { $w = $d.workspace.git_worktree }
            return New-Text $w
        }
        'pr' {
            $pr = $d.pr
            if (($null -eq $pr) -or ($null -eq $pr.number)) { return $null }
            $state = ''; $url = ''
            if ($null -ne $pr.review_state) { $state = [string]$pr.review_state }
            if ($null -ne $pr.url) { $url = [string]$pr.url }
            return [ordered]@{ value = [string]$pr.number; state = $state; url = $url }
        }
        'rate_5h' { return Get-Limit $d.rate_limits.five_hour }
        'rate_7d' { return Get-Limit $d.rate_limits.seven_day }
        'spend' { return Get-Limit $d.rate_limits.spend_limit }
        'cache_hit' {
            $h = $d.prompt_cache.hit_ratio
            if ($null -eq $h) { return $null }
            $v = Get-Pct ([double]$h * 100)
            return [ordered]@{ value = [string]$v; n = $v }
        }
        'cache_ttl' {
            $e = $d.prompt_cache.expires_at
            if (($null -eq $e) -or ([double]$e -le $script:now)) { return $null }
            return [ordered]@{ value = (Format-Human ([double]$e - $script:now)) }
        }
    }
    return $null
}

$defaults = @{
    'user' = '{value}'; 'host' = '{value}'; 'folder' = '{value}'; 'ctx_used' = '{k}'; 'ctx_max' = '{k}'
    'ctx_pct' = '{value}%'; 'model' = '{value}'; 'effort' = '{value}'; 'fast_mode' = '{value}'
    'thinking' = '{value}'; 'output_style' = '{value}'; 'vim_mode' = '{value}'; 'session_name' = '{value}'
    'cost' = '${value}'; 'duration' = '{value}'; 'api_duration' = '{value}'; 'lines_added' = '+{value}'
    'lines_removed' = '-{value}'; 'repo' = '{value}'; 'branch' = '{value}'; 'worktree' = '{value}'
    'pr' = 'PR #{value}'; 'rate_5h' = '5h {value}%'; 'rate_7d' = '7d {value}%'; 'spend' = '{value}%'
    'cache_hit' = 'cache {value}%'; 'cache_ttl' = '{value}'
}

$colourNames = @{ 'black' = 0; 'red' = 1; 'green' = 2; 'yellow' = 3; 'blue' = 4; 'magenta' = 5; 'cyan' = 6; 'white' = 7 }

function Get-Ansi($colour) {
    if ($null -eq $colour) { return $null }
    if (($colour -is [int]) -or ($colour -is [long]) -or ($colour -is [double]) -or ($colour -is [decimal])) {
        return '38;5;' + [string][long][Math]::Floor([double]$colour)
    }
    $c = [string]$colour
    if ($c -match '^[0-9]+$') { return '38;5;' + $c }
    if ($c -match '^#[0-9a-fA-F]{6}$') {
        $r = [Convert]::ToInt32($c.Substring(1, 2), 16)
        $g = [Convert]::ToInt32($c.Substring(3, 2), 16)
        $b = [Convert]::ToInt32($c.Substring(5, 2), 16)
        return "38;2;$r;$g;$b"
    }
    if ($c.StartsWith('bright_')) {
        $base = $c.Substring(7)
        if ($colourNames.ContainsKey($base)) { return [string]($colourNames[$base] + 90) }
        return $null
    }
    if ($colourNames.ContainsKey($c)) { return [string]($colourNames[$c] + 30) }
    return $null
}

function Get-ThresholdColour($seg, $n) {
    if ((-not (Test-Has $seg 'thresholds')) -or ($null -eq $n)) { return $seg.color }
    if (($null -eq $seg.thresholds) -or ($seg.thresholds -is [string]) -or
        ($seg.thresholds -is [System.Management.Automation.PSCustomObject])) { return $seg.color }
    foreach ($rule in $seg.thresholds) {
        if (-not ($rule -is [System.Management.Automation.PSCustomObject])) { continue }
        $below = $null
        try { if ($null -ne $rule.below) { $below = [double]$rule.below } } catch { $below = $null }
        if (($null -eq $below) -or ([double]$n -lt $below)) {
            if ($null -ne $rule.color) { return $rule.color }
            return $seg.color
        }
    }
    return $seg.color
}

function Format-Styled([string]$text, $seg, $colour) {
    # Control characters would reach the terminal as escape sequences; drop them.
    $text = $text -replace '[\x00-\x1F\x7F]', ''
    $codes = @()
    if ($seg.bold -eq $true) { $codes += '1' }
    $code = Get-Ansi $colour
    if ($null -ne $code) { $codes += $code }
    if ($script:noColour -or ($codes.Count -eq 0) -or ($text -eq '')) { return $text }
    return $esc + '[' + ($codes -join ';') + 'm' + $text + $esc + '[0m'
}

function Format-Fill([string]$format, $r) {
    foreach ($key in @($r.Keys)) {
        if ($key -eq 'n') { continue }
        $format = $format.Replace('{' + $key + '}', [string]$r[$key])
    }
    return $format
}

function Format-Line($line) {
    $segs = @()
    foreach ($seg in $line) {
        if (-not ($seg -is [System.Management.Automation.PSCustomObject])) { continue }
        if (Test-Has $seg 'item') {
            try { $r = Get-Value ([string]$seg.item) $seg } catch { $r = $null }
            $filled = ''
            if ($null -ne $r) {
                $format = $defaults[[string]$seg.item]
                if (Test-Has $seg 'format') { $format = [string]$seg.format }
                try { $filled = Format-Fill $format $r } catch { $filled = '' }
            }
            if ($filled -eq '') {
                $segs += , @{ kind = 'item'; shown = $false; out = '' }
            } else {
                $n = $null
                if ($r.Contains('n')) { $n = $r['n'] }
                $out = Format-Styled $filled $seg (Get-ThresholdColour $seg $n)
                $segs += , @{ kind = 'item'; shown = $true; out = $out }
            }
        } elseif (Test-Has $seg 'sep') {
            $segs += , @{ kind = 'sep'; shown = $false; out = (Format-Styled ([string]$seg.sep) $seg $seg.color) }
        } else {
            $text = ''
            if (Test-Has $seg 'text') { $text = [string]$seg.text }
            $segs += , @{ kind = 'text'; shown = $false; out = (Format-Styled $text $seg $seg.color) }
        }
    }
    $shownAt = @()
    for ($i = 0; $i -lt $segs.Count; $i++) { if ($segs[$i].shown) { $shownAt += $i } }
    if ($shownAt.Count -eq 0) { return $null }
    $text = ''
    for ($i = 0; $i -lt $segs.Count; $i++) {
        $s = $segs[$i]
        if ($s.kind -ne 'sep') { $text += $s.out; continue }
        $prev = -1; $next = -1
        foreach ($j in $shownAt) {
            if ($j -lt $i) { $prev = $j }
            if (($j -gt $i) -and ($next -lt 0)) { $next = $j }
        }
        if (($prev -lt 0) -or ($next -lt 0)) { continue }
        $earlier = $false
        for ($k = $prev + 1; $k -lt $i; $k++) { if ($segs[$k].kind -eq 'sep') { $earlier = $true } }
        if (-not $earlier) { $text += $s.out }
    }
    return $text
}

# Runs git with a one-second limit; returns its first output line, or ''.
function Invoke-Git([string]$folder, [string]$arguments) {
    try {
        $info = New-Object System.Diagnostics.ProcessStartInfo
        $info.FileName = 'git'
        $info.Arguments = '-C "' + $folder + '" ' + $arguments
        $info.UseShellExecute = $false
        $info.RedirectStandardOutput = $true
        $info.RedirectStandardError = $true
        $info.CreateNoWindow = $true
        $process = [System.Diagnostics.Process]::Start($info)
        $output = $process.StandardOutput.ReadLineAsync()
        if (-not $process.WaitForExit(1000)) { $process.Kill(); return '' }
        if ($process.ExitCode -ne 0) { return '' }
        $line = $output.Result
        if ($null -eq $line) { return '' }
        return $line.Trim()
    } catch {
        return ''
    }
}

# --- main ---

$reader = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), $utf8)
$raw = $reader.ReadToEnd()

$dir = $env:STATUSLINE_DIR
if (Test-Empty $dir) { $dir = Join-Path (Join-Path $HOME '.claude') 'statusline' }
$presetPath = $env:STATUSLINE_PRESET
if (Test-Empty $presetPath) {
    $active = $null
    $configPath = Join-Path $dir 'config.json'
    if (Test-Path -LiteralPath $configPath) {
        try { $active = (Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json).active } catch { $active = $null }
    }
    if (Test-Empty $active) { Stop-With 'no config' }
    $presetPath = Join-Path (Join-Path $dir 'presets') ([string]$active + '.json')
}
if (-not (Test-Path -LiteralPath $presetPath -PathType Leaf)) {
    Stop-With ('preset ' + $quote + [IO.Path]::GetFileNameWithoutExtension($presetPath) + $quote + ' not found')
}
try {
    $presetText = Get-Content -LiteralPath $presetPath -Raw -Encoding UTF8
    $preset = ConvertFrom-Json $presetText
} catch {
    Stop-With 'invalid preset'
}
$valid = ($null -ne $preset) -and (Test-Has $preset 'lines') -and ($preset.lines -is [array])
if ($valid) { foreach ($line in $preset.lines) { if (-not ($line -is [array])) { $valid = $false } } }
if (-not $valid) { Stop-With 'invalid preset' }
foreach ($line in $preset.lines) {
    foreach ($seg in $line) {
        if (-not ($seg -is [System.Management.Automation.PSCustomObject])) { continue }
        if ((Test-Has $seg 'item') -and (-not $defaults.ContainsKey([string]$seg.item))) {
            Stop-With ('unknown item ' + $quote + [string]$seg.item + $quote)
        }
    }
}

try {
    $script:data = ConvertFrom-Json $raw
} catch {
    Stop-With 'invalid input'
}
if ($null -eq $script:data) { exit 0 }

$script:user = $env:STATUSLINE_USER
if (Test-Empty $script:user) { $script:user = [Environment]::UserName }
$script:hostName = $env:STATUSLINE_HOST
if (Test-Empty $script:hostName) { $script:hostName = [Environment]::MachineName }
$script:homeDir = $env:STATUSLINE_HOME
if (Test-Empty $script:homeDir) { $script:homeDir = $HOME }
if (Test-Empty $env:STATUSLINE_NOW) { $script:now = [double][DateTimeOffset]::UtcNow.ToUnixTimeSeconds() }
else { $script:now = [double]$env:STATUSLINE_NOW }
$script:noColour = $env:STATUSLINE_NO_COLOR -eq '1'
$script:utc = $env:STATUSLINE_UTC -eq '1'

# The input does not carry the git branch, so ask git, only when the preset shows it.
$script:branch = ''
if ($presetText -match '"item"\s*:\s*"branch"') {
    $folder = $script:data.workspace.current_dir
    if (Test-Empty $folder) { $folder = $script:data.cwd }
    if (Test-Empty $folder) { $folder = (Get-Location).Path }
    if ((Test-Path -LiteralPath $folder -PathType Container) -and (Get-Command git -ErrorAction SilentlyContinue)) {
        $script:branch = Invoke-Git $folder 'symbolic-ref --short -q HEAD'
        if ($script:branch -eq '') { $script:branch = Invoke-Git $folder 'rev-parse --short HEAD' }
    }
}

$lines = @()
foreach ($line in $preset.lines) {
    $text = Format-Line $line
    if ($null -ne $text) { $lines += $text }
}
if ($lines.Count -gt 0) { Write-Output-Text (($lines -join "`n") + "`n") }
exit 0
