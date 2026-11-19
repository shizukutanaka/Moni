$ErrorActionPreference = 'Stop'

$packages = @(Get-ChildItem -LiteralPath dist -Filter '*.exe' -File)
if ($packages.Count -ne 1) {
    throw "Expected one Windows release EXE, found $($packages.Count)"
}

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("moni-windows-package-" + [guid]::NewGuid())
$launcher = $null
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
    $exe = Join-Path $tmp $packages[0].Name
    $profile = Join-Path $tmp 'profile'
    Copy-Item -LiteralPath $packages[0].FullName -Destination $exe
    $launcher = Start-Process -FilePath $exe -WorkingDirectory $tmp -PassThru `
        -ArgumentList ('--user-data-dir="' + $profile + '"')

    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($timer.Elapsed.TotalSeconds -lt 45) {
        if ($launcher.HasExited) {
            throw "Portable launcher exited before Moni opened (code $($launcher.ExitCode))"
        }

        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $($launcher.Id) AND Name = 'Moni.exe'"
        foreach ($child in $children) {
            $moni = Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
            if ($moni -and $moni.MainWindowTitle -like 'Moni*PC Device Info Viewer') {
                if (!$moni.CloseMainWindow() -or !$launcher.WaitForExit(10000) -or $launcher.ExitCode -ne 0) {
                    throw 'Moni opened but the portable launcher did not exit cleanly'
                }
                Write-Output 'PASS | Windows portable EXE opens the Moni window and exits cleanly'
                return
            }
        }
        Start-Sleep -Milliseconds 250
    }
    throw 'Timed out waiting for the Moni window'
} finally {
    if ($launcher -and !$launcher.HasExited) {
        & taskkill.exe /PID $launcher.Id /T /F | Out-Null
        $launcher.WaitForExit(10000) | Out-Null
    }
    Remove-Item -LiteralPath $tmp -Recurse -Force
}
