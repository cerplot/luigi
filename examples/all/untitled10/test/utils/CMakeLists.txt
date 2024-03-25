target_sources(utils_test PRIVATE main.cc logger_test.cc config_test.cc)
target_link_libraries(utils_test gtest gtest_main utils)  # Link with Google Test libraries
target_include_directories(utils_test PRIVATE ${CMAKE_SOURCE_DIR}/src/utils)
target_include_directories(utils_test PRIVATE ${CMAKE_SOURCE_DIR}/lib/tomlpp/include/toml++)