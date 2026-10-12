# Finish the Afon -> Mushegh rename: the parts that need elevation.
#
# The repo moved from C:\Afon to C:\Mushegh (the package was already renamed to `mushegh` in
# pyproject.toml, but the Windows Scheduled Tasks were never re-registered), so these tasks
# still point at a dead path AND a module that no longer exists:
#
#   AfonEdge         -> C:\Afon\.venv\Scripts\pythonw.exe -m afon.edge.assistant   (RunLevel Limited)
#   AfonPcAgent      -> C:\Afon\.venv\Scripts\pythonw.exe -m afon.edge.pc_agent    (RunLevel Highest)
#   AfonEdgeRefresh  -> C:\Afon\scripts\restart_edge.ps1                           (RunLevel Limited)
#   AfonEdgeGuard    -> wscript .openclaw\afon-guard-hidden.vbs                    (Disabled)
#
# Everything in the codebase that names a task (protocols.py goodnight/phoenix, restart_edge.ps1,
# autostart.py, SOP.md, TESTING_GUIDE.md) expects the canonical Mushegh* names, so while these
# Afon* tasks exist the goodnight/phoenix protocols are no-ops against a missing task.
#
# MusheghPcAgent cannot be re-registered from a normal session ("Access is denied") because it runs
# at RunLevel Highest. This script therefore must run elevated; it re-registers the other three by
# transforming their exported XML (so triggers, principal and settings carry over byte-for-byte
# instead of being guessed at), replaces the guard with the repo's own installer, then starts the edge.
#
# Run elevated:  powershell -ExecutionPolicy Bypass -File C:\Mushegh\scripts\finish_afon_rename.ps1
# Register only:  powershell -ExecutionPolicy Bypass -File C:\Mushegh\scripts\finish_afon_rename.ps1 -SkipStart

[CmdletBinding()]
param([switch]$SkipStart)

$ErrorActionPreference = 'Stop'

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
          ).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Elevating (approve the UAC prompt)..." -ForegroundColor Yellow
    Start-Process powershell.exe -Verb RunAs -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"",
        '-SkipStart:$SkipStart'
    )
    return
}

$map = [ordered]@{
    'AfonEdge'        = 'MusheghEdge'
    'AfonPcAgent'     = 'MusheghPcAgent'
    'AfonEdgeRefresh' = 'MusheghEdgeRefresh'
}

foreach ($old in $map.Keys) {
    $new = $map[$old]
    if (-not (Get-ScheduledTask -TaskName $old -ErrorAction SilentlyContinue)) {
        Write-Host "  $old already gone, skipping" -ForegroundColor DarkGray
        continue
    }
    # Transform the exported XML rather than rebuilding the task, so triggers, principal
    # and settings carry over byte-for-byte instead of being guessed at.
    $xml = Export-ScheduledTask -TaskName $old
    $xml = $xml.Replace('C:\Afon', 'C:\Mushegh').
                Replace('afon.edge', 'mushegh.edge').
                Replace('-m afon', '-m mushegh').
                Replace('afon-guard', 'mushegh-guard')
    Register-ScheduledTask -TaskName $new -Xml $xml -Force | Out-Null
    Unregister-ScheduledTask -TaskName $old -Confirm:$False
    Write-Host "  $old -> $new" -ForegroundColor Green
}

# The old guard launched a VBS shim outside the repo (.openclaw\afon-guard-hidden.vbs) whose paths are
# gone. Replace it with the repo's own installer, which embeds the edge check inline and therefore has
# no external file to keep in sync.
if (Get-ScheduledTask -TaskName 'AfonEdgeGuard' -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName 'AfonEdgeGuard' -Confirm:$False
    Write-Host "  AfonEdgeGuard removed (replaced by the repo installer)" -ForegroundColor Green
}
if (-not (Get-ScheduledTask -TaskName 'MusheghEdgeGuard' -ErrorAction SilentlyContinue)) {
    & (Join-Path $PSScriptRoot 'install_edge_guard.ps1')
    Write-Host "  MusheghEdgeGuard registered" -ForegroundColor Green
} else {
    Enable-ScheduledTask -TaskName 'MusheghEdgeGuard' | Out-Null
    Write-Host "  MusheghEdgeGuard re-enabled" -ForegroundColor Green
}

if ($SkipStart) {
    Write-Host "`n  -SkipStart given: tasks registered, edge left stopped." -ForegroundColor Cyan
} else {
    foreach ($t in 'MusheghPcAgent', 'MusheghEdge') {
        if (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue) {
            Start-ScheduledTask -TaskName $t
            Start-Sleep -Milliseconds 1500
        }
    }
    Start-Sleep -Seconds 6

    $edge = @(Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'")
    Write-Host ("`n  pythonw processes now running: {0}" -f $edge.Count) -ForegroundColor Cyan
    foreach ($p in $edge) {
        $cl = if ($p.CommandLine) { $p.CommandLine } else { '(elevated - command line not readable)' }
        Write-Host ("    " + $cl)
    }
}

Write-Host "`n  Remaining Mushegh tasks:" -ForegroundColor Cyan
Get-ScheduledTask | Where-Object { $_.TaskName -match 'Mushegh|Afon|Watari|Jarvis' } |
    ForEach-Object { Write-Host ("    " + $_.TaskName + "  [" + $_.State + "]") }

$stale = Get-ScheduledTask | Where-Object { $_.TaskName -match '^(Afon|Watari|Jarvis)' }
if ($stale) {
    Write-Host "`n  WARNING: stale-named tasks still present:" -ForegroundColor Red
    $stale | ForEach-Object { Write-Host ("    " + $_.TaskName) -ForegroundColor Red }
} else {
    Write-Host "`n  No Afon*/Watari*/Jarvis* tasks remain." -ForegroundColor Green
}

Write-Host "`n== done ==" -ForegroundColor Cyan
Start-Sleep -Seconds 3