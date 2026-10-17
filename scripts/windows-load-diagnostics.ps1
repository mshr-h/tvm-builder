$ErrorActionPreference = 'Stop'
$debuggers = "${env:ProgramFiles(x86)}/Windows Kits/10/Debuggers/x64"
$cdb = Join-Path $debuggers 'cdb.exe'
$gflags = Join-Path $debuggers 'gflags.exe'
if (-not (Test-Path $cdb)) { throw 'The Windows SDK x64 debugger is required' }
$python = (Resolve-Path 'tmp/.test-venv/Scripts/python.exe').Path
$basePython = & $python -c 'import sys; print(sys._base_executable)'
$env:TVM_DIAGNOSTIC_SITE_PACKAGES = (Resolve-Path 'tmp/.test-venv/Lib/site-packages').Path
$log = Join-Path $env:GITHUB_WORKSPACE 'build-metrics/windows-load.log'
$symbolPath = "$env:GITHUB_WORKSPACE/build/lib;$env:GITHUB_WORKSPACE/3rdparty/tvm-ffi/build/lib;$env:GITHUB_WORKSPACE/tirx/build/lib;$env:GITHUB_WORKSPACE/tirx/3rdparty/tvm-ffi/build/lib;srv*$env:RUNNER_TEMP/symbols*https://msdl.microsoft.com/download/symbols"
$probe = Join-Path $env:RUNNER_TEMP 'tvm-load-probe.py'
@'
import os
import sys
sys.path.insert(0, os.environ['TVM_DIAGNOSTIC_SITE_PACKAGES'])
import tvm_ffi
print('FFI imported', flush=True)
import tvm
print('TVM imported', flush=True)
os.environ['TVM_TEST_TARGETS'] = 'llvm'
os.environ['TVM_WHEEL_EXPECT_LLVM'] = '1'
import pytest
raise SystemExit(pytest.main(['-v', os.path.join(os.environ['GITHUB_WORKSPACE'], 'tests/python/all-platform-minimal-test')]))
'@ | Set-Content -Path $probe -Encoding utf8
$onFault = 'kpn; !avrf; !analyze -v; .ecxr; kpn; lm; q'
$commands = "sxd ibp; sxe -c `"$onFault`" bpe; sxe -c `"$onFault`" av; sxe -c `"$onFault`" 0xc0000374; g"
& $gflags /p /enable python.exe /full
try {
    # Debug the interpreter directly, with only the test venv's installed wheels.
    # -g would postpone initial commands until the verifier stop itself.
    & $cdb -G -logo $log -y $symbolPath -c $commands $basePython -S $probe
} finally {
    & $gflags /p /disable python.exe
}
if (Test-Path $log) { Get-Content $log }
if (Select-String -Path $log -Pattern 'VERIFIER STOP|Access violation - code c0000005|Heap corruption - code c0000374' -Quiet) {
    throw 'Native wheel validation detected heap corruption or an access violation; inspect windows-load.log'
}
