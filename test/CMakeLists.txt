cmake_minimum_required(VERSION 3.24)
# 'Google_test' is the subproject name
project(Google_tests)
# Find the Google Test package
add_subdirectory(lib)
include_directories(${gtest_SOURCE_DIR}/include ${gtest_SOURCE_DIR})
# Add the test executable
add_executable(Google_Tests_run "testconfig/trade_engin_test.cpp" "testconfig/config_test.cpp")

# Include the tomlplusplus library
target_include_directories(Google_Tests_run PRIVATE "../tomlplusplus-3.4.0/include/toml++")
target_include_directories(Google_Tests_run PRIVATE "../src")

# Link the Google Test libraries and the Google_tests_lib library to the Google_Tests_run executable
target_link_libraries(Google_Tests_run gtest gtest_main untitled7_lib)
