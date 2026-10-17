#include <tvm/ffi/container/list.h>

#include <iostream>

int original_buffer_releases = 0;

struct ListCellAccess : tvm::ffi::ListObj {
  static TVMFFISeqCell* Cell(tvm::ffi::ListObj* object) {
    return static_cast<TVMFFISeqCell*>(object);
  }
};

void OriginalBufferDelete(void* data) {
  ++original_buffer_releases;
  ::operator delete(data);
}

int main() {
  {
    tvm::ffi::List<tvm::ffi::Any> values{1, 2, 3, 4};
    ListCellAccess::Cell(values.GetListObj())->data_deleter = OriginalBufferDelete;
    for (int i = 5; i <= 40; ++i) values.push_back(i);
    if (values.size() != 40) return 2;
    for (int i = 0; i < 40; ++i) {
      if (values[i].cast<int>() != i + 1) return 3;
    }
  }
  std::cout << "Original buffer releases: " << original_buffer_releases << std::endl;
  // Growth consumes the original buffer once. Further growth and destruction
  // must use the deleter paired with each replacement allocation.
  return original_buffer_releases == 1 ? 0 : 1;
}
