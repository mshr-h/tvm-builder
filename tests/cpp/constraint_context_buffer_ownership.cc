#include <tvm/sym/analyzer.h>

#include <iostream>

int main() {
  tvm::sym::Analyzer analyzer;
  tvm::PrimVar x("constraint_buffer_probe");
  for (int i = 0; i < 32; ++i) {
    {
      // EnterWithScope allocates the recovery vector in the core DLL, while
      // this executable constructs and destroys the context on its stack.
      tvm::With<tvm::sym::ConstraintContext> scope(analyzer, x >= 0);
      if (!analyzer->CanProve(x >= 0)) return 1;
    }
    if (analyzer->CanProve(x >= 0)) return 2;
  }
  std::cout << "Cross-DLL constraint entry, recovery and destruction passed" << std::endl;
  return 0;
}
