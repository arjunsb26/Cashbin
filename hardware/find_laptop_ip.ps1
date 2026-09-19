# Print the address the bin should dial, and the whole command to dial it with.
#
# Run this on the laptop that runs the backend:
#
#     powershell -ExecutionPolicy Bypass -File hardware\find_laptop_ip.ps1
#
# The mobile hotspot adapter wins, because the demo plan is the laptop sharing its
# connection and the bin and the phone joining that. Windows gives the hotspot
# 192.168.137.1 and hands the bin something in the same range. Wi-Fi comes next, for
# the case where everything is on one ordinary network instead.

$ErrorActionPreference = 'Stop'

function Get-Candidates {
    Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.PrefixOrigin -ne 'WellKnown' } |
        ForEach-Object {
            $adapter = Get-NetAdapter -InterfaceIndex $_.InterfaceIndex -ErrorAction SilentlyContinue
            [pscustomobject]@{
                Address = $_.IPAddress
                Adapter = if ($adapter) { $adapter.Name } else { "interface $($_.InterfaceIndex)" }
                Kind    = if ($adapter) { $adapter.InterfaceDescription } else { '' }
                Up      = if ($adapter) { $adapter.Status -eq 'Up' } else { $true }
            }
        }
}

function Get-Rank {
    param($Candidate)
    if ($Candidate.Address -like '192.168.137.*') { return 0 }   # Windows mobile hotspot
    if ($Candidate.Kind -match 'Wi-?Fi|Wireless|802\.11') { return 1 }
    if ($Candidate.Adapter -match 'Wi-?Fi') { return 1 }
    if ($Candidate.Address -like '169.254.*') { return 9 }       # no address really
    return 5
}

$candidates = @(Get-Candidates | Where-Object { $_.Up })
if ($candidates.Count -eq 0) {
    Write-Host 'No network adapter has an address. Turn the mobile hotspot on, or join a network.'
    exit 1
}

$ranked = $candidates | Sort-Object @{ Expression = { Get-Rank $_ } }, Address
$best = $ranked[0]

Write-Host ''
Write-Host 'Addresses this laptop has:'
foreach ($item in $ranked) {
    $mark = if ($item.Address -eq $best.Address) { 'use' } else { '   ' }
    Write-Host ("{0} {1,-16} {2}" -f $mark, $item.Address, $item.Adapter)
}

Write-Host ''
Write-Host 'Point the bin at this:'
Write-Host ''
Write-Host ("    ws://{0}:8000/ws/bin" -f $best.Address)
Write-Host ''
Write-Host 'The whole command, on the board:'
Write-Host ''
Write-Host ("    python3 bridge.py --url ws://{0}:8000/ws/bin --source bridge" -f $best.Address)
Write-Host ''
Write-Host 'The dashboard, from another machine on the same network:'
Write-Host ''
Write-Host ("    http://{0}:3000" -f $best.Address)
Write-Host ''

if ($best.Address -notlike '192.168.137.*') {
    Write-Host 'The mobile hotspot is off. Turn it on for the demo, in Settings, Network'
    Write-Host 'and internet, Mobile hotspot, then run this again.'
    Write-Host ''
}
