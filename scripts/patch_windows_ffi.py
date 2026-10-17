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


def patch(source_root):
    patch_ffi(source_root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path, nargs="?", default=Path("."))
    patch(parser.parse_args().source_root)
