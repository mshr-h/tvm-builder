$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$vswhere = "${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe"
$vsInstall = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vsInstall) { throw 'An x64 MSVC toolchain is required' }
& "$vsInstall/Common7/Tools/Launch-VsDevShell.ps1" -Arch amd64 -HostArch amd64 -SkipAutomaticLocation
$python = (Resolve-Path 'tmp/.test-venv/Scripts/python.exe').Path
$ffiCmake = & $python -m tvm_ffi.config --cmakedir
$ffiLib = & $python -m tvm_ffi.config --libdir
$checkArgs = @('-S', '.ci/tests/cpp', '-B', 'tmp/ffi-buffer-test', '-G', 'Ninja',
    "-Dtvm_ffi_DIR=$ffiCmake", "-DPython_EXECUTABLE=$python", '-DCMAKE_BUILD_TYPE=Release',
    '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded')
$hasTirx = & $python -c "import importlib.util; print(int(importlib.util.find_spec('tvm_tirx') is not None))"
if ($hasTirx -eq '1') {
    $tirxCmake = & $python -m tvm_tirx.config --cmakedir
    $tirxLib = & $python -m tvm_tirx.config --libdir
    $checkArgs += @('-DTVM_CHECK_FUNCTOR_OWNERSHIP=ON', "-Dtvm_tirx_DIR=$tirxCmake")
    $env:PATH = "$tirxLib;$env:PATH"
}
cmake @checkArgs
cmake --build tmp/ffi-buffer-test --parallel 4
$env:PATH = "$ffiLib;$env:PATH"
& ./tmp/ffi-buffer-test/ffi_list_buffer_ownership.exe
if ($hasTirx -eq '1') {
    & ./tmp/ffi-buffer-test/object_functor_buffer_ownership.exe
}
