# tvm-builder
Build [Apache TVM](https://github.com/apache/tvm) with GitHub Actions

The weekly workflow builds the latest TVM `main` for Linux, macOS, and Windows
with Python 3.11–3.15. All builds enable LLVM; Linux also enables CUDA and macOS
enables Metal.
Python 3.15 uses uv's managed stable CPython distribution; earlier versions use
`actions/setup-python`.

MLIR is disabled because TVM's MLIR-enabled build currently fails to compile with
an undefined `kSimplifyRewriteCanonicalRewrite` symbol. Re-enable it after the
upstream compatibility issue is resolved.

Windows builds supply LLVM's missing `libxml2s.lib` by building libxml2 v2.9.12
for x64 with Release, static libraries, and the static MSVC runtime, using the
feature settings from the [LLVM 21.1.8 release build script](https://github.com/llvm/llvm-project/blob/llvmorg-21.1.8/llvm/utils/release/build_llvm_release.bat).
TVM uses the same static MSVC runtime on Windows. The optional Z3 solver is
disabled there because the prebuilt static Z3 library uses the dynamic MSVC
runtime. Windows wheel builds use MSVC with Ninja and four parallel build jobs.

Windows applies a guarded FFI List buffer ownership fix: reallocation must
replace the deleter along with the buffer so allocation and deallocation stay
in the same DLL. Retaining the previous DLL's deleter caused heap corruption
during TVM compiler initialization. A C++ regression checks the installed FFI
headers after the clean wheel import and minimal tests.
The split TIRx build also binds `ObjectFunctor`'s vector allocator to the DLL
that owns the table. This prevents a second DLL from freeing a buffer created
while initializing inherited visitor dispatch. A C++ regression extends and
finalizes a core-initialized table from a separate executable.

Pull requests validate all 15 configurations, including installing all local
wheels with their dependencies, checking LLVM and the OS's required CUDA/Metal support, running TVM's minimal
tests, and uploading the wheels. Releases run only on pushes to `main` and the
weekly schedule. The manual Windows workflow validates Python 3.11–3.15 and
uploads a separate artifact for each Python version.

TVM's split package layout builds FFI, TIRx, and TVM from the same source
checkout, in dependency order. The build environment installs the local FFI
and TIRx wheels before building their consumers; the clean test environment
installs all three wheels together. Older commits with the combined TVM layout
remain supported. All generated wheels are collected in `wheelhouse/` for
validation and artifact/release upload.
Linux explicitly links with lld because the official LLVM static archives
contain bitcode and the standalone TIRx build does not select lld automatically.

Both workflows use sccache v0.18.0 for TVM, TIRx, and FFI compilation, including CUDA
and Metal compiler launchers. Windows uses embedded MSVC debug information
(`/Z7`) to avoid shared PDB files; a CMake hook replaces FFI's explicit `/Zi`
target flag. A local cache of up to 3 GiB per OS is restored with `actions/cache`.
Keys separate OS, architecture, and compiler/SDK versions;
Python versions share compiler objects when their inputs match. Python 3.11
is the sole cache writer on each OS and saves after compilation, before tests.
New TVM revisions can restore the previous compatible snapshot; sccache checks
the source, headers, and compiler flags before reusing an object.

The job summary and `build-metrics-*` artifacts record per-package build times,
compiler cache hits/misses, restore time, cache size, source SHAs, and toolchain
versions. Build requirements are installed from each source project's
`pyproject.toml` into the job's dedicated environment to avoid random isolated-build paths.
Local source-built packages satisfy build requirements instead of downloading
prebuilt core wheels.
Every attempt removes the CMake build trees and validates the resulting wheels
in a fresh test environment. Rerunning a workflow preserves its original TVM
SHA in a run-scoped cache and records it in the `tvm-source` artifact, making
cold/warm comparisons reproducible. If that cache has been evicted, reruns
require an explicit benchmark ref or a new run instead of changing source.
Each new weekly run still resolves the latest TVM `main`.
For a controlled benchmark, label a PR `cache-benchmark` before pushing:
attempt 1 forces recompilation in every configuration, and a workflow rerun
uses the saved cache. Ordinary PR and weekly runs use any compatible cache
immediately.
Benchmark runs queue subsequent heads so expensive cache seeds can finish.
For labelled benchmark PRs, the optional repository variable `TVM_BENCHMARK_REF`
pins a TVM commit across workflow edits. Setting `CACHE_BENCHMARK_COLD=false`
allows the first attempt of a new workflow run to use the existing snapshot.
These controls do not change weekly source selection. TVM's global version
define changes with new revisions and can invalidate otherwise reusable
compiler objects; same-SHA measurements do not establish weekly-update gains.

The manual Windows workflow can select a TVM commit/ref and one Python version,
with all versions and latest TVM `main` as the defaults. Its optional native
load diagnostics enable page heap and capture the Windows SDK debugger's stack
after an import failure; the failed wheel test keeps the workflow unsuccessful.
The `native-diagnostics` PR label enables the same diagnostics for the Windows
Python 3.11 job, including the minimal LLVM test, while retaining the PR cache scope.

## Todos

- [ ] Add Google Colab notebook
