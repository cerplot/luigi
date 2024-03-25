cmake_minimum_required(VERSION 3.24)
set(CMAKE_CXX_STANDARD 20)
# copy examples directory to build directory every build:
#add_custom_target(copy_examples_directory ALL
#        COMMAND ${CMAKE_COMMAND} -E copy_directory
#        ${CMAKE_SOURCE_DIR}/examples ${CMAKE_BINARY_DIR}/examples)
# copy on config stage:
file(COPY ${CMAKE_SOURCE_DIR}/examples DESTINATION ${CMAKE_BINARY_DIR})

add_executable(utils_test utils/config_test.cc utils/logger_test.cc)
add_subdirectory(utils)