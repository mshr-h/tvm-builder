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
runtime. Windows TVM builds use MSVC with Ninja and four parallel build jobs.

Pull requests validate all 15 configurations, including installing both local
wheels with their dependencies, checking LLVM support, running TVM's minimal
tests, and uploading the wheels. Releases run only on pushes to `main` and the
weekly schedule. The manual Windows workflow validates Python 3.11–3.15 and
uploads a separate artifact for each Python version.

Both workflows use sccache v0.18.0 for TVM and FFI compilation, including CUDA
and Metal compiler launchers. Windows uses embedded MSVC debug information
(`/Z7`) to avoid shared PDB files; a CMake hook replaces FFI's explicit `/Zi`
target flag. A local cache of up to 3 GiB per OS is restored with `actions/cache`.
Keys separate OS, architecture, and compiler/SDK versions;
Python versions share compiler objects when their inputs match. Python 3.11
is the sole cache writer on each OS and saves after compilation, before tests.
New TVM revisions can restore the previous compatible snapshot; sccache checks
the source, headers, and compiler flags before reusing an object.

The job summary and `build-metrics-*` artifacts record TVM/FFI build times,
compiler cache hits/misses, restore time, cache size, source SHAs, and toolchain
versions. Build requirements are installed from both upstream `pyproject.toml`
files into the job's dedicated environment to avoid random isolated-build paths.
Every attempt removes the CMake build trees and validates the resulting wheels
in a fresh test environment. Rerunning a workflow preserves its original TVM
SHA in the `tvm-source` artifact, making cold/warm comparisons reproducible.
Each new weekly run still resolves the latest TVM `main`.
For a controlled benchmark, label a PR `cache-benchmark` before pushing:
attempt 1 forces recompilation in every configuration, and a workflow rerun
uses the saved cache. Ordinary PR and weekly runs use any compatible cache
immediately.

## Todos

- [ ] Add Google Colab notebook
