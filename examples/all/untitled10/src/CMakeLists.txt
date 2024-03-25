cmake_minimum_required(VERSION 3.24)
set(CMAKE_CXX_STANDARD 20)

add_executable(te main.cc engine.cc engine.h)
add_subdirectory(utils)
add_subdirectory(core)
add_subdirectory(steps)
target_link_libraries(te utils)
