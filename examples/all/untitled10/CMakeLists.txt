cmake_minimum_required(VERSION 3.24)
project(
        trade_engine
        VERSION 0.1
        DESCRIPTION "A simple trade engine"
        LANGUAGES CXX
)

add_subdirectory(src)
add_subdirectory(test)
add_subdirectory(lib/google)