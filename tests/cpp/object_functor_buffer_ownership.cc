#include <tvm/ffi/object.h>
#include <tvm/tirx/stmt_functor.h>

#include <iostream>

struct ProbeNode : tvm::ffi::Object {
  TVM_FFI_DECLARE_OBJECT_INFO("test.ObjectFunctorBuffer", ProbeNode, tvm::ffi::Object);
};

struct ProbeVisitor : tvm::tirx::StmtExprVisitor {
  static bool Check() {
    VTable table;
    // The core DLL initializes the table, then this executable extends it.
    tvm::tirx::StmtExprVisitor::InitVTable(&table);
    table.SetDispatch<ProbeNode>(
        [](const tvm::ffi::Object*, tvm::ObjectVisitor*)
            -> tvm::ffi::Optional<tvm::ffi::VisitInterrupt> { return std::nullopt; });
    table.Finalize();
    auto node = tvm::ffi::ObjectRef(tvm::ffi::make_object<ProbeNode>());
    return table.CanDispatch(node);
  }
};

int main() {
  if (!ProbeVisitor::Check()) return 1;
  std::cout << "Cross-DLL ObjectFunctor growth, finalization and destruction passed" << std::endl;
  return 0;
}
