# Compile the bin sketch, put it on the UNO Q, and watch the first JSON lines.
#
#   powershell -ExecutionPolicy Bypass -File hardware\uno_q\flash.ps1
#   powershell -ExecutionPolicy Bypass -File hardware\uno_q\flash.ps1 -Port COM7
#   powershell -ExecutionPolicy Bypass -File hardware\uno_q\flash.ps1 -CompileOnly
#
# Compile only needs no board, which is how the sketch was proven before the board
# arrived. Everything else needs the board plugged into the laptop with USB-C.

[CmdletBinding()]
param(
  [string]$Port = "",
  [int]$MonitorSeconds = 10,
  [switch]$CompileOnly,
  [switch]$NoMonitor
)

$ErrorActionPreference = "Stop"

$Fqbn = "arduino:zephyr:unoq"
$SketchDir = Join-Path $PSScriptRoot "sketch"
$Baud = 115200

# Where arduino-cli is ----------------------------------------------------------

function Find-ArduinoCli {
  $onPath = Get-Command arduino-cli -ErrorAction SilentlyContinue
  if ($onPath) { return $onPath.Source }
  $local = "D:\codering\tools\arduino-cli\arduino-cli.exe"
  if (Test-Path $local) { return $local }
  throw "arduino-cli is not installed. See hardware/README.md, section 1."
}

$Cli = Find-ArduinoCli
Write-Host "arduino-cli  $Cli"
& $Cli version
Write-Host ""

# Which display the sketch is built for, so the log says it out loud --------------

$config = Get-Content (Join-Path $SketchDir "bin_config.h") -Raw
$driver = if ($config -match '#define USE_ILI9341 1') { "ILI9341" }
          elseif ($config -match '#define USE_ST7789 1') { "ST7789" }
          else { "none, and the build will stop" }
$rpc = if ($config -match '#define USE_APP_LAB_RPC 1') { "the App Lab router bridge" } else { "serial JSON lines" }
Write-Host "display driver  $driver"
Write-Host "host link       $rpc"
Write-Host ""

# Compile -------------------------------------------------------------------------

Write-Host "compiling $SketchDir"
& $Cli compile --fqbn $Fqbn $SketchDir
if ($LASTEXITCODE -ne 0) { throw "the sketch did not compile, so nothing was uploaded" }
Write-Host ""

if ($CompileOnly) {
  Write-Host "compile only, stopping here"
  exit 0
}

# Find the board ------------------------------------------------------------------

function Find-BoardPort {
  $json = & $Cli board list --format json 2>$null | ConvertFrom-Json
  $ports = @()
  if ($json -is [array]) { $ports = $json } elseif ($json.detected_ports) { $ports = $json.detected_ports }

  # Named first: the core recognises the board and tells us the FQBN.
  foreach ($p in $ports) {
    foreach ($b in @($p.matching_boards)) {
      if ($b.fqbn -eq $Fqbn) { return $p.port.address }
    }
  }
  # Then by the UNO Q's USB identity, from `arduino-cli board details`.
  foreach ($p in $ports) {
    $props = $p.port.properties
    if ($props -and $props.vid -match '2341' -and $props.pid -match '0078') { return $p.port.address }
  }
  return ""
}

if ($Port -eq "") { $Port = Find-BoardPort }

if ($Port -eq "") {
  Write-Host ""
  Write-Host "No UNO Q found on a port. The sketch compiled, so this is a cable or a mode"
  Write-Host "problem, not a code problem. Three things to try, in order:"
  Write-Host ""
  Write-Host "  1. USB-C into the board's own port, not a hub, and wait ten seconds for the"
  Write-Host "     Linux side to finish booting. Then run this script again."
  Write-Host "  2. Pass the port by hand once you know it:"
  Write-Host "       -Port COM7"
  Write-Host "     Run arduino-cli board list to see every port this laptop has."
  Write-Host "  3. On the UNO Q the Linux side owns the USB port, so the documented way in"
  Write-Host "     is the board itself. See hardware/uno_q/board_linux_setup.md, which has"
  Write-Host "     the shell, the wifi and the bridge."
  exit 2
}

Write-Host "board on $Port"
Write-Host ""

# Upload ---------------------------------------------------------------------------

Write-Host "uploading"
& $Cli upload -p $Port --fqbn $Fqbn $SketchDir
if ($LASTEXITCODE -ne 0) { throw "the upload failed on $Port" }
Write-Host "uploaded"
Write-Host ""

if ($NoMonitor) { exit 0 }

# Watch ------------------------------------------------------------------------------

Write-Host "watching $Port for $MonitorSeconds seconds at $Baud baud"
Write-Host ""
Write-Host "What you want to see is one JSON object per line, about twenty a second:"
Write-Host '  {"t":123456,"g":0.00}'
Write-Host ""
Write-Host "Nothing at all is expected in two cases, and neither is a fault:"
Write-Host "  - USE_APP_LAB_RPC is 1, so the weights go over the router bridge, not a wire."
Write-Host "  - USE_APP_LAB_RPC is 0, and the lines leave on D0 and D1, which need a USB to"
Write-Host "    serial adapter of their own. hardware/README.md section 9 has the wiring."
Write-Host ""

$log = Join-Path ([System.IO.Path]::GetTempPath()) "binbooks_monitor.txt"
if (Test-Path $log) { Remove-Item $log -Force }

$proc = Start-Process -FilePath $Cli `
  -ArgumentList @("monitor", "-p", $Port, "--fqbn", $Fqbn, "-c", "baudrate=$Baud") `
  -RedirectStandardOutput $log -NoNewWindow -PassThru

Start-Sleep -Seconds $MonitorSeconds
if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 400

if (Test-Path $log) {
  $lines = Get-Content $log -ErrorAction SilentlyContinue
  if ($lines) {
    Write-Host "--- first 20 lines ---"
    $lines | Select-Object -First 20 | ForEach-Object { Write-Host $_ }
    Write-Host "--- $($lines.Count) lines in $MonitorSeconds seconds ---"
  } else {
    Write-Host "nothing arrived on $Port, which the two notes above may explain"
  }
  Remove-Item $log -Force -ErrorAction SilentlyContinue
}
