"""Keep Windows container buffers paired with their allocating DLL."""

import argparse
from pathlib import Path


def patch_ffi(source_root):
    ffi_root = source_root / "tirx/3rdparty/tvm-ffi"
    if not ffi_root.exists():
        ffi_root = source_root / "3rdparty/tvm-ffi"
    header = ffi_root / "include/tvm/ffi/container/list.h"
    source = header.read_text(encoding="utf-8")
    old = "    data_deleter(data);\n    data = new_data;\n    TVMFFISeqCell::capacity = n;"
    fixed = "    data_deleter(data);\n    data = new_data;\n    data_deleter = RawDataDeleter;\n    TVMFFISeqCell::capacity = n;"
    if fixed in source:
        print(f"FFI List buffer ownership is already fixed: {header}")
        return
    if source.count(old) != 1:
        raise RuntimeError(f"Unsupported FFI List::Reserve shape in {header}; inspect upstream ownership handling")
    header.write_text(source.replace(old, fixed), encoding="utf-8")
    print(f"Paired reallocated FFI List buffers with their allocating DLL: {header}")


def patch_functor(source_root):
    if not (source_root / "tirx/pyproject.toml").exists():
        return
    header = source_root / "tirx/include/tvm/ir/object_functor.h"
    source = header.read_text(encoding="utf-8")
    old = "  std::vector<FPointer> func_;"
    fixed = "  std::vector<FPointer, detail::ObjectFunctorAllocator<FPointer>> func_;"
    if fixed in source and "class ObjectFunctorAllocator" in source:
        print(f"ObjectFunctor buffer ownership is already fixed: {header}")
        return
    if source.count(old) != 1 or source.count("namespace tvm {\n") != 1:
        raise RuntimeError(f"Unsupported ObjectFunctor storage in {header}; inspect upstream DLL ownership")
    allocator = Path(__file__).with_name("windows-object-functor-allocator.h").read_text(encoding="utf-8")
    source = source.replace("#include <cstring>", "#include <cstring>\n#include <limits>\n#include <new>")
    source = source.replace("namespace tvm {\n", "namespace tvm {\n\n" + allocator + "\n", 1)
    header.write_text(source.replace(old, fixed), encoding="utf-8")
    print(f"Bound ObjectFunctor buffer allocation and release to one DLL: {header}")


def patch(source_root):
    patch_ffi(source_root)
    patch_functor(source_root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path, nargs="?", default=Path("."))
    patch(parser.parse_args().source_root)
