$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$vswhere = "${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe"
$vsInstall = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vsInstall) { throw 'An x64 MSVC toolchain is required' }
& "$vsInstall/Common7/Tools/Launch-VsDevShell.ps1" -Arch amd64 -HostArch amd64 -SkipAutomaticLocation

# LLVM's Windows static Support archive embeds rpmalloc and replaces the CRT
# allocator in whichever DLL links it. TVM passes STL containers between the
# LLVM-linked core and DLLs using the CRT, so those allocators must agree.
$support = Join-Path $env:LLVM_ROOT 'lib/LLVMSupport.lib'
$nm = Join-Path $env:LLVM_ROOT 'bin/llvm-nm.exe'
$members = @(& lib.exe /nologo /list $support)
$allocatorMembers = @($members | Where-Object { $_ -match '(^|[\\/])rpmalloc\.c\.obj$' })
if ($allocatorMembers.Count -gt 1) { throw 'Unexpected multiple rpmalloc members in LLVMSupport.lib' }
$beforeHash = (Get-FileHash $support -Algorithm SHA256).Hash
$removed = $null
if ($allocatorMembers.Count -eq 1) {
    $removed = $allocatorMembers[0]
    $modified = "$support.crt.lib"
    & lib.exe /nologo $support "/REMOVE:$removed" "/OUT:$modified"
    $remaining = @(& lib.exe /nologo /list $modified)
    $difference = @(Compare-Object $members $remaining -PassThru)
    if ($difference.Count -ne 1 -or $difference[0] -ne $removed) {
        throw 'Allocator removal changed other LLVMSupport library members'
    }
    Move-Item -Force $modified $support
}
$symbols = @(& $nm --defined-only $support)
if ($symbols | Where-Object { $_ -match 'rpmalloc|rpfree|\b[TW]\s+(malloc|free|_malloc_base|_free_base)$' }) {
    throw 'LLVMSupport still contains CRT allocator overrides; inspect this LLVM distribution'
}
New-Item -ItemType Directory -Force build-metrics | Out-Null
[ordered]@{
    llvm_version = $env:LLVM_VERSION
    library = $support
    removed_member = $removed
    original_sha256 = $beforeHash
    modified_sha256 = (Get-FileHash $support -Algorithm SHA256).Hash
} | ConvertTo-Json | Set-Content -Encoding utf8 build-metrics/llvm-allocator.json
Write-Host "LLVM DLL consumers use the CRT allocator; removed member: $removed"
