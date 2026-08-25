$ErrorActionPreference = "Stop"
$matlabCode = "C:\MY DATA ANALYTICS FILES AND PROJECTS\MAJOR\AI-Adaptive-Transceiver\OTFS MRC detection MATLAB code"
$matlabExe = "C:\MY DATA ANALYTICS FILES AND PROJECTS\Matlab\bin\matlab.exe"
$logFile = Join-Path $matlabCode "Results\FinalEvaluation\matlab_remaining.log"

Set-Content $logFile "=== MATLAB Launch: $(Get-Date) ===`n"

Set-Location $matlabCode

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $matlabExe
$psi.Arguments = "-batch"
$psi.WorkingDirectory = $matlabCode
$psi.UseShellExecute = $false
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $false

$proc = [System.Diagnostics.Process]::Start($psi)

$matlabCmd = @"
cd('$($matlabCode.Replace('\','\\'))');
addpath('.');
run('Results/FinalEvaluation/run_remaining.m');
exit;
"@

$proc.StandardInput.WriteLine($matlabCmd)
$proc.StandardInput.Close()

$stdout = $proc.StandardOutput.ReadToEnd()
$stderr = $proc.StandardError.ReadToEnd()

$proc.WaitForExit()

Add-Content $logFile $stdout
if ($stderr) {
    Add-Content $logFile "`n=== STDERR ==="
    Add-Content $logFile $stderr
}
Add-Content $logFile "`n=== Exit code: $($proc.ExitCode) ==="
Add-Content $logFile "=== MATLAB Finished: $(Get-Date) ==="

Write-Output "MATLAB finished, exit code: $($proc.ExitCode)"
Write-Output "Log written to: $logFile"
