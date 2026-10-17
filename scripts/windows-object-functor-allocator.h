// A shared dispatch table can grow in several DLLs. Keep its allocator's
// entry points with the table, so every buffer uses one DLL's CRT.
namespace detail {
template <typename T>
class ObjectFunctorAllocator {
 public:
  using value_type = T;
  using propagate_on_container_move_assignment = std::true_type;
  using is_always_equal = std::false_type;

  ObjectFunctorAllocator() noexcept : allocate_(Allocate), deallocate_(Deallocate) {}
  template <typename U>
  ObjectFunctorAllocator(const ObjectFunctorAllocator<U>& other) noexcept
      : allocate_(other.allocate_), deallocate_(other.deallocate_) {}

  T* allocate(std::size_t count) {
    if (count > std::numeric_limits<std::size_t>::max() / sizeof(T)) {
      throw std::bad_array_new_length();
    }
    return static_cast<T*>(allocate_(count * sizeof(T), alignof(T)));
  }
  void deallocate(T* data, std::size_t) noexcept { deallocate_(data, alignof(T)); }

  template <typename U>
  bool operator==(const ObjectFunctorAllocator<U>& other) const noexcept {
    return allocate_ == other.allocate_ && deallocate_ == other.deallocate_;
  }
  template <typename U>
  bool operator!=(const ObjectFunctorAllocator<U>& other) const noexcept {
    return !(*this == other);
  }

 private:
  static void* Allocate(std::size_t bytes, std::size_t alignment) {
    if (alignment > __STDCPP_DEFAULT_NEW_ALIGNMENT__) {
      return ::operator new(bytes, std::align_val_t(alignment));
    }
    return ::operator new(bytes);
  }
  static void Deallocate(void* data, std::size_t alignment) noexcept {
    if (alignment > __STDCPP_DEFAULT_NEW_ALIGNMENT__) {
      ::operator delete(data, std::align_val_t(alignment));
    } else {
      ::operator delete(data);
    }
  }

  void* (*allocate_)(std::size_t, std::size_t);
  void (*deallocate_)(void*, std::size_t) noexcept;
  template <typename>
  friend class ObjectFunctorAllocator;
};
}  // namespace detail
