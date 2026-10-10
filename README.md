# tvm-builder
Build [Apache TVM](https://github.com/apache/tvm) with GitHub Actions

The weekly workflow builds the latest TVM `main` for Linux, macOS, and Windows
with Python 3.10–3.14. All builds enable LLVM; Linux also enables CUDA and macOS
enables Metal.

MLIR is disabled because TVM's MLIR-enabled build currently fails to compile with
an undefined `kSimplifyRewriteCanonicalRewrite` symbol. Re-enable it after the
upstream compatibility issue is resolved.

Windows builds supply LLVM's missing `libxml2s.lib` by building libxml2 v2.9.12
for x64 with Release, static libraries, and the static MSVC runtime, using the
feature settings from the [LLVM 21.1.8 release build script](https://github.com/llvm/llvm-project/blob/llvmorg-21.1.8/llvm/utils/release/build_llvm_release.bat).

Pull requests validate all 15 configurations, including installing both local
wheels with their dependencies, checking LLVM support, running TVM's minimal
tests, and uploading the wheels. Releases run only on pushes to `main` and the
weekly schedule. The manual Windows workflow validates Python 3.10–3.14 and
uploads a separate artifact for each Python version.

## Todos

- [ ] Add Google Colab notebook
