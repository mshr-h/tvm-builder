$ErrorActionPreference = 'Stop'
$debuggers = "${env:ProgramFiles(x86)}/Windows Kits/10/Debuggers/x64"
$cdb = Join-Path $debuggers 'cdb.exe'
$gflags = Join-Path $debuggers 'gflags.exe'
if (-not (Test-Path $cdb)) { throw 'The Windows SDK x64 debugger is required' }
$python = (Resolve-Path 'tmp/.test-venv/Scripts/python.exe').Path
$log = Join-Path $env:GITHUB_WORKSPACE 'build-metrics/windows-load.log'
$symbolPath = "$env:GITHUB_WORKSPACE/build/lib;$env:GITHUB_WORKSPACE/3rdparty/tvm-ffi/build/lib;$env:GITHUB_WORKSPACE/tirx/build/lib;$env:GITHUB_WORKSPACE/tirx/3rdparty/tvm-ffi/build/lib;srv*$env:RUNNER_TEMP/symbols*https://msdl.microsoft.com/download/symbols"
$probe = Join-Path $env:RUNNER_TEMP 'tvm-load-probe.py'
@'
import tvm_ffi
print('FFI imported', flush=True)
import tvm
print('TVM imported', flush=True)
'@ | Set-Content -Path $probe -Encoding utf8
$commands = 'sxe -c "!analyze -v; .ecxr; kpn; lm; q" av; sxe -c "!analyze -v; .ecxr; kpn; lm; q" 0xc0000374; g'
& $gflags /p /enable python.exe /full
try {
    # Windows virtualenv Python launches the actual interpreter as a child.
    & $cdb -o -g -G -logo $log -y $symbolPath -c $commands $python $probe
} finally {
    & $gflags /p /disable python.exe
}
if (Test-Path $log) { Get-Content $log }
